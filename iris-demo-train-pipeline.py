import os
import time
import kfp
from kfp import compiler, dsl
from kfp.components import create_component_from_func, InputPath, func_to_container_op

from kubernetes.client.models import V1LocalObjectReference

from kubernetes import client, config
from utils import add_nfs_volume, add_configmap, KubeflowClient, add_sharedmemory


def read_mlflow_run_id(run_id_path: InputPath):
    with open(run_id_path, 'r') as f:
        return f.read().strip()


@kfp.dsl.pipeline(
    name="IRIS Model Training Pipeline",
    description="",
)
def iris_demo_train_pipeline(
    lakefs_date: str = "2025-04-08-104352/",
    download_lakefs_image: str = "<REGISTRY_HOST>/iris/demo/00-kubeflow-function/lakefs-function:latest",
    train_model_image: str = "<REGISTRY_HOST>/iris/demo/02-model-training:latest",
    random_state: int = 42,
    max_iter: int = 1000,
    multi_class: str = "multinomial",
):
    # ----- Temporary volume create ----- #
    vop = dsl.VolumeOp(
        name="Temporary volume create",
        storage_class="k8s-nfs",
        resource_name="tmp-volume",
        modes=dsl.VOLUME_MODE_RWM,     # ReadWriteMany
        size="1Gi",
    ).add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")


    # ----- Download datasets ----- #
    download_datasets_op = (
        dsl.ContainerOp(
            name="Download Datasets",
            image=download_lakefs_image,
            command=["python", "lakefs_download.py"],
            arguments=[
                "--root", "/mnt/preprocessed",
                "--repo", "demo-iris",
                "--date", lakefs_date,
            ],
            pvolumes={"/mnt": vop.volume},
        )
        .add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")
        .after(vop)
    )
    add_configmap(download_datasets_op, configmap_name="lakefs-config")


    # ----- Train Model ----- #
    train_model_op = (
        dsl.ContainerOp(
            name="Train Model",
            image=train_model_image,
            command=["python", "train.py"],
            arguments=[
                "--data_path", "/mnt/preprocessed",
                "--random_state", random_state,
                "--max_iter", max_iter,
                "--multi_class", multi_class,
            ],
            pvolumes={"/mnt": vop.volume},
            file_outputs={
                'mlpipeline-ui-metadata': '/mnt/outputs/mlpipeline-ui-metadata.json',
                'mlflow_run_id': '/mnt/outputs/mlflow_run_id.txt'
            }
        )
        .add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")
        .after(download_datasets_op)
    )
    # train_model_op.container.set_gpu_limit(1)
    add_configmap(train_model_op, configmap_name="mlflow-config")
    # add_sharedmemory(train_model_op)
    
    read_mlflow_run_id_op = dsl.ContainerOp(
        name="Read MLflow Run ID",
        image="python:3.9",
        command=["sh", "-c"],
        arguments=[
            f"echo {train_model_op.outputs['mlflow_run_id']}"
        ],
    ).after(train_model_op)
    
    
    # ----- Model Deployment ----- #
    model_deployment_op = (
        dsl.ContainerOp(
            name="Model Deployment",
            image="<REGISTRY_HOST>/iris/demo/00-kubeflow-function/mlflow-function:latest",
            command=["python", "mlflow_model_register.py"],
            arguments=[
                "--experiment_name", "[DEMO]Iris_Training",
                "--model_name", "[DEMO]Iris_Training",
                "--filter", "accuracy",
                "--order_by", "DESC",
            ],
            file_outputs={"update_info": "/workspace/update.json"},
        )
        .add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D"  )
        .after(train_model_op)
    )
    add_configmap(model_deployment_op, configmap_name="mlflow-config")
    
    


if __name__ == "__main__":
    # ----- build ----- #
    pipeconf = kfp.dsl.PipelineConf()
    pipeconf.set_image_pull_secrets([V1LocalObjectReference("harbor")])
    pipeconf.set_image_pull_policy("Always")
    pipeconf.set_default_pod_node_selector(label_name="nodetype", value="kwg1")

    KUBEFLOW_ENDPOINT = os.environ.get("KUBEFLOW_ENDPOINT", "http://<KUBEFLOW_HOST>:30080")
    KUBEFLOW_USERNAME = os.environ.get("KUBEFLOW_USERNAME", "user@example.com")
    KUBEFLOW_PASSWORD = os.environ.get("KUBEFLOW_PASSWORD", "")
    KUBEFLOW_NAMESPACE = os.environ.get("KUBEFLOW_NAMESPACE", "kubeflow-user-example-com")

    # Create pkg directory if it doesn't exist
    os.makedirs("./00-DEMO-iris/package", exist_ok=True)
    
    file_name = "iris-demo-train-pipeline"
    compiler.Compiler().compile(iris_demo_train_pipeline, f"./00-DEMO-iris/package/{file_name}.tar.gz", pipeline_conf=pipeconf)

    try:
        client = KubeflowClient(
            endpoint=KUBEFLOW_ENDPOINT,
            username=KUBEFLOW_USERNAME,
            password=KUBEFLOW_PASSWORD,
            namespace=KUBEFLOW_NAMESPACE,
        )
        res = client.upload_pipeline(f"./00-DEMO-iris/package/{file_name}.tar.gz", "iris-demo-train-pipeline")
        print("업로드 결과:", res)
    except Exception as e:
        print("에러 발생:", str(e))
        
    print("파이프라인 목록:", client.client.list_pipelines())