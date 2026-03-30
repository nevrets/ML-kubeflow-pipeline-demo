import os
import time
import kfp
from kfp import compiler, dsl
from kubernetes.client.models import V1LocalObjectReference

from kubernetes import client, config
from utils import add_nfs_volume, add_configmap, KubeflowClient


@kfp.dsl.pipeline(
    name="IRIS Demo Data Pipeline",
    description="",
)
def iris_demo_data_pipeline(
    nfs_path: str = "<NFS_SERVER_IP>",
    dataset_path: str = "/volume1/kubernetes/iris",
    load_data_image: str = "<REGISTRY_HOST>/iris/demo/01-data-loading:latest",
    upload_lakefs_image: str = "<REGISTRY_HOST>/iris/demo/00-kubeflow-function/lakefs-function:latest",
):
    # ----- Temporary volume create ----- #
    vop = dsl.VolumeOp(
        name="Temporary volume create",
        storage_class="k8s-nfs",
        resource_name="tmp-volume",
        modes=dsl.VOLUME_MODE_RWM,     # ReadWriteMany
        size="1Gi",
    ).add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")

    # ----- Load iris data ----- #
    load_op = dsl.ContainerOp(
        name="load iris data",
        image=load_data_image,
        command=["python", "load_data.py"],
        arguments=[
            "--data_path", "/mnt/nfs/iris",
            "--output_path", "/mnt/preprocessed",
        ],
        pvolumes={"/mnt": vop.volume},    # 임시 볼륨 경로
    ).add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")
    add_nfs_volume(
        load_op,
        volume_name="nfs",
        nfs_server=nfs_path,           
        nfs_path=dataset_path,         # NFS 서버의 실제 경로
        mount_path="/mnt/nfs/iris",    # 컨테이너에서 실제로 마운트할 경로
    )

    # ----- Upload to lakefs ----- #
    upload_op = (
        dsl.ContainerOp(
            name="upload to lakefs",
            image=upload_lakefs_image,
            command=["python", "lakefs_upload.py"],
            arguments=[
                "--root", "/mnt/preprocessed",
                "--repo", "demo-iris",
                "--branch", "main",
            ],
            pvolumes={"/mnt": vop.volume},
        )
        .add_pod_annotation(name="pipelines.kubeflow.org/max_cache_staleness", value="P0D")
        .after(load_op)
    )
    add_configmap(upload_op, configmap_name="lakefs-config")


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


    file_name = os.path.splitext(os.path.basename(__file__))[0]
    compiler.Compiler().compile(iris_demo_data_pipeline, f"./00-DEMO-iris/package/{file_name}.tar.gz", pipeline_conf=pipeconf)

    try:
        client = KubeflowClient(
            endpoint=KUBEFLOW_ENDPOINT,
            username=KUBEFLOW_USERNAME,
            password=KUBEFLOW_PASSWORD,
            namespace=KUBEFLOW_NAMESPACE,
        )
        res = client.upload_pipeline(f"./00-DEMO-iris/package/{file_name}.tar.gz", "iris-demo-data-pipeline")
        print("업로드 결과:", res)
    except Exception as e:
        print("에러 발생:", str(e))
        
    print("파이프라인 목록:", client.client.list_pipelines())