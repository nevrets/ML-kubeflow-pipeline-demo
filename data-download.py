import os

import kfp
from kfp import compiler, dsl
from kubernetes.client.models import V1LocalObjectReference

from utils import *


@kfp.dsl.pipeline(
    name="ESM SSSD Model Training Pipeline",
    description="",
)
def sssd_training_pipeline(
    lakefs_date: str = "2024-10-06-160546",
    lakefs_sequence_length: int = 600,
    dataset_configs={
        "dataset_dir": "/mnt/SSSD_datasets",
        "segment_length": 600,
        "sampling_rate": 600,
        "batch_size": 16,
    },
    model_configs={
        "T": 200,
        "beta_0": 0.0001,
        "beta_T": 0.02,
        "in_channels": 3,
        "out_channels": 3,
        "num_res_layers": 36,
        "res_channels": 256,
        "skip_channels": 256,
        "diffusion_step_embed_dim_in": 128,
        "diffusion_step_embed_dim_mid": 512,
        "diffusion_step_embed_dim_out": 512,
        "s4_lmax": 600,
        "s4_d_state": 64,
        "s4_dropout": 0.0,
        "s4_bidirectional": 1,
        "s4_layernorm": 1,
        "only_generate_missing": 1,
        "use_model": 2,
        "masking": "bm",
        "missing_k": 90,
    },
    train_configs={
        "output_directory": "/mnt/results/",
        "ckpt_iter": "max",
        "iters_per_ckpt": 10,
        "iters_per_logging": 100,
        "n_iters": 1,
        "learning_rate": 0.0002,
        "gen_output_directory": "/mnt/results/",
        "ckpt_path": "/mnt/results/",
        "gpu_num": 0,
    },
):
    # ----- Temporary volume create ----- #
    vop = dsl.VolumeOp(
        name="Temporary volume create",
        storage_class="k8s-nfs",
        resource_name="tmp-volume",
        modes=dsl.VOLUME_MODE_RWM,
        size="1Gi",
    ).add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")

    # ----- datasets download ----- #
    datasets_download_op = (
        dsl.ContainerOp(
            name="Dataset Download",
            image=f"192.168.25.15:30002/funzin/engagement-support/kubeflow-function/lakefs-function:latest",
            command=["python3", "lakefs_download.py"],
            arguments=[
                "--root",
                "/mnt/SSSD_datasets",
                "--repo",
                "esm",
                "--date",
                lakefs_date,
                "--sequence_length",
                lakefs_sequence_length,
            ],
            pvolumes={"/mnt": vop.volume},
        )
        .add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")
        .after(vop)
    )
    add_configmap(datasets_download_op, configmap_name="lakefs-config")

    # ----- Model training ----- #
    training_op = (
        dsl.ContainerOp(
            name="Model Training",
            image=f"192.168.25.15:30002/funzin/engagement-support/models/sssd:latest",
            command=["python3", "train_mias_class.py"],
            arguments=[
                "--dataset_configs",
                dataset_configs,
                "--model_configs",
                model_configs,
                "--train_configs",
                train_configs,
            ],
            pvolumes={"/mnt": vop.volume},
        )
        .add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")
        .after(datasets_download_op)
    )
    training_op.container.set_gpu_limit(1)
    add_configmap(training_op, configmap_name="mlflow-config")
    add_sharedmemory(training_op)
    
    # ----- Model deployment ----- #
    model_deployment_op = (
        dsl.ContainerOp(
            name="Model Deployment",
            image=f"192.168.25.15:30002/funzin/engagement-support/kubeflow-function/mlflow-function:latest",
            command=["python3", "mlflow_model_register.py"],
            arguments=[
                "--experiment_name",
                "[Engagement_Support]SSSD",
                "--model_name",
                "[Engagement_Support]SSSD",
                "--filter",
                "val_loss",
                "--order_by",
                "ASC",
            ],
            file_outputs={"update_info": "/workspace/update.json"},
        )
        .add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")
        .after(training_op)
    )
    add_configmap(model_deployment_op, configmap_name="mlflow-config")


if __name__ == "__main__":
    # ----- build ----- #
    pipeconf = kfp.dsl.PipelineConf()
    pipeconf.set_image_pull_secrets([V1LocalObjectReference("harbor")])
    pipeconf.set_image_pull_policy("Always")
    pipeconf.set_default_pod_node_selector(label_name="nodetype", value="train")

    file_name = os.path.splitext(os.path.basename(__file__))[0]
    compiler.Compiler().compile(sssd_training_pipeline, f"pkg/{file_name}.tar.gz", pipeline_conf=pipeconf)

    KUBEFLOW_ENDPOINT = "http://192.168.25.15:30593"
    KUBEFLOW_USERNAME = "user@example.com"
    KUBEFLOW_PASSWORD = "12341234"
    KUBEFLOW_NAMESPACE = "kubeflow-user-example-com"
    client = KubeflowClient(
        endpoint=KUBEFLOW_ENDPOINT,
        username=KUBEFLOW_USERNAME,
        password=KUBEFLOW_PASSWORD,
        namespace=KUBEFLOW_NAMESPACE,
    )

    res = client.upload_pipeline(f"pkg/{file_name}.tar.gz", "esm-sssd-training-pipeline")
    print(res)
