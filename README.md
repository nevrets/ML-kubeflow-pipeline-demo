# Kubeflow Pipeline Demo — Iris

Iris 데이터셋을 활용한 Kubeflow Pipeline 데모 프로젝트
데이터 적재부터 모델 학습 및 MLflow 등록까지의 ML 파이프라인

## 파이프라인 구성

### Data Pipeline (`iris-demo-data-pipeline.py`)
```
Load Iris Data (NFS) → Upload to LakeFS
```

### Training Pipeline (`iris-demo-train-pipeline.py`)
```
Download from LakeFS → Train Model → Register to MLflow
```

## 프로젝트 구조

```
├── 00-kubeflow-function/
│   ├── configmap/              # Kubernetes ConfigMap 템플릿
│   │   ├── lakefs-config.yaml
│   │   └── mlflow-config.yaml
│   ├── lakefs-function/        # LakeFS 데이터 업로드/다운로드
│   │   ├── lakefs.py
│   │   ├── lakefs_upload.py
│   │   └── lakefs_download.py
│   └── mlflow-function/        # MLflow 모델 등록/다운로드
│       ├── mlflow_model_register.py
│       └── mlflow_model_downloader.py
├── 01-data-loading/            # 데이터 로딩 컨테이너
│   ├── load_data.py
│   └── Dockerfile
├── 02-model-training/          # 모델 학습 컨테이너
│   ├── train.py
│   └── Dockerfile
├── iris-demo-data-pipeline.py  # KFP 데이터 파이프라인 정의
├── iris-demo-train-pipeline.py # KFP 학습 파이프라인 정의
├── iris-pipeline.yaml          # 컴파일된 파이프라인 YAML
├── utils.py                    # Kubeflow 클라이언트 유틸리티
└── podman-build.sh             # 컨테이너 이미지 빌드 스크립트
```

## 기술 스택

| 역할 | 도구 |
|------|------|
| ML 파이프라인 오케스트레이션 | Kubeflow Pipelines |
| 데이터 버저닝 | LakeFS |
| 실험 추적 / 모델 레지스트리 | MLflow |
| 오브젝트 스토리지 | MinIO |
| 컨테이너 빌드 | Podman |

## 환경 설정

### 필수 환경변수

**LakeFS** (`lakefs-config` ConfigMap)
```bash
LAKEFS_ACCESS_KEY_ID=<your-access-key>
LAKEFS_SECRET_ACCESS_KEY=<your-secret-key>
LAKEFS_URL=http://<lakefs-host>:<port>
MINIO_URL=http://<minio-host>:<port>
MINIO_ACCESS_KEY=<your-access-key>
MINIO_SECRET_KEY=<your-secret-key>
```

**MLflow** (`mlflow-config` ConfigMap)
```bash
MLFLOW_TRACKING_URI=http://<mlflow-host>:<port>
MLFLOW_S3_ENDPOINT_URL=http://<minio-host>:<port>
AWS_ACCESS_KEY_ID=<minio-access-key>
AWS_SECRET_ACCESS_KEY=<minio-secret-key>
MLFLOW_S3_BUCKET=mlflow
```

**Kubeflow** (파이프라인 실행 시)
```bash
export KUBEFLOW_ENDPOINT=http://<kubeflow-host>:<port>
export KUBEFLOW_USERNAME=<username>
export KUBEFLOW_PASSWORD=<password>
export KUBEFLOW_NAMESPACE=<namespace>
```

## 실행 방법

### 1. 컨테이너 이미지 빌드
```bash
export REGISTRY_HOST=<your-registry>
bash podman-build.sh
```

### 2. ConfigMap 적용
```bash
# 실제 값 입력 후 적용
kubectl apply -f 00-kubeflow-function/configmap/lakefs-config.yaml
kubectl apply -f 00-kubeflow-function/configmap/mlflow-config.yaml
```

### 3. 파이프라인 업로드
```bash
python iris-demo-data-pipeline.py
python iris-demo-train-pipeline.py
```

## 의존성 설치

```bash
pip install -r requirements.txt
```
