import io
import hashlib
import base64
import json
import boto3
import requests
import os
from loguru import logger

import lakefs_client
from lakefs_client import models
from lakefs_client.client import LakeFSClient
from lakefs_client.client import LakeFSClient

LAKEFS_ACCESS_KEY_ID = os.environ["LAKEFS_ACCESS_KEY_ID"]
LAKEFS_SECRET_ACCESS_KEY = os.environ["LAKEFS_SECRET_ACCESS_KEY"]
LAKEFS_URL = os.environ["LAKEFS_URL"]
MINIO_URL = os.environ["MINIO_URL"]
MINIO_ACCESS_KEY = os.environ["MINIO_ACCESS_KEY"]
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]

class LakeFS:
    
    def __init__(self) -> None:
        self.lakefs_access_key = LAKEFS_ACCESS_KEY_ID
        self.lakefs_secret_key = LAKEFS_SECRET_ACCESS_KEY
        self.lakefs_endpoint = LAKEFS_URL
        
        # LakeFS credentials and endpoint
        self.configuration = lakefs_client.Configuration(
            username = self.lakefs_access_key,
            password = self.lakefs_secret_key,
            host = self.lakefs_endpoint
        )
        
        # MinIO credentials and endpoint
        self.minio_client = boto3.client(
            's3',
            endpoint_url=MINIO_URL,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY
        )
        
        # LakeFS auth header
        self.auth_header = self.get_auth_header()

        
    def create_bucket(self, repository):
        try:
            self.minio_client.create_bucket(Bucket=repository)
            logger.info(f'Create bucket name: {repository}')
        except:
            logger.info(f'Already own MinIO bucket: {repository}')
            pass 
        
    def upload_to_minio(self, repository, minio_key, file_content):
        if repository is not None:
            self.create_bucket(repository)
            
        self.minio_client.put_object(Bucket=repository, Key=minio_key, Body=file_content)
        
    def import_to_lakefs(self, repository, branch, path, file_content):
        if repository is not None:
            self.create_lakefs_repository(repository, branch)
            self.check_and_create_branch(repository, branch)
            
        minio_key = f'{repository}/{branch}/{path}'
        self.upload_to_minio(repository, minio_key, file_content)
        
        physical_address = f's3://{repository}/{branch}/{path}'

        upload_url = f'{self.lakefs_endpoint}/repositories/{repository}/branches/{branch}/objects'
        upload_headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json'
        }

        md5_checksum = hashlib.md5(file_content).hexdigest()
        upload_data = {
            'physical_address': physical_address,
            'checksum': md5_checksum,
            'size_bytes': len(file_content),
            'content_type': 'application/octet-stream'
        }

        upload_response = requests.put(upload_url, headers=upload_headers, params={'path': path}, data=json.dumps(upload_data))

        if upload_response.status_code == 201:
            # print('File metadata registered successfully in lakeFS')
            pass
        else:
            logger.error(f'File metadata registration failed: {upload_response.text}')
            
    
    def commit_to_lakefs(self, repository, branch):
        commit_url = f'{self.lakefs_endpoint}/repositories/{repository}/branches/{branch}/commits'
        commit_payload = {'message': 'Initial commit'}

        commit_headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json'
        }

        commit_response = requests.post(commit_url, headers=commit_headers, data=json.dumps(commit_payload))

        if commit_response.status_code == 201:
            msg = 'Commit successful'
        else:
            msg = f'Commit failed: {commit_response.text}'
            
        return msg
    
    def get_lakefs_file_content(self, repository, branch, file_name):
        client = LakeFSClient(self.configuration)
        try:
            # lakeFS에서 파일 가져오기
            response = client.objects.get_object(repository=repository, ref=branch, path=file_name)
            # 파일 내용 읽기
            file_content = response.read().decode('utf-8')
            return file_content
        
        except Exception as e:
            logger.error("Error:", e)
            return None

    def create_repository(self, repository, branch):
        client = LakeFSClient(self.configuration)

        try:
            # Create repository
            repository_creation = models.RepositoryCreation(name=repository, 
                                                            storage_namespace=f's3://{repository}', 
                                                            default_branch=branch)
            
            client.repositories.create_repository(repository_creation)
            logger.info("Repository created successfully.")

        except:
            # print(f'Already own LakeFS repository: {self.repository}')
            pass
        
    def create_lakefs_repository(self, repository):
        self.create_bucket(repository)
        client = LakeFSClient(self.configuration)
        
        try:
            repository_creation = models.RepositoryCreation(
                name=repository,
                description="",
                storage_namespace=f"s3://{repository}",
            )
            client.repositories.create_repository(repository_creation)
            logger.info(f"Repository created successfully: {repository}")
            
            # # Create a branch in the repository
            # branch_creation = models.BranchCreation(
            #     name=self.branch,
            #     source="main"  # 기본 소스 브랜치를 'main'으로 설정
            # )
            # client.branches.create_branch(self.repository, branch_creation)
            # print("Branch created successfully")
            
        except:
            # print(f'Already own LakeFS repository: {self.repository}')
            pass

    def check_and_create_branch(self, repository, branch):        
        branch_url = f'{self.lakefs_endpoint}/repositories/{repository}/branches/{branch}'
        branch_headers = {'Authorization': f'Basic {self.auth_header}'}

        branch_response = requests.get(branch_url, headers=branch_headers)

        if branch_response.status_code == 404:
            create_branch_url = f'{self.lakefs_endpoint}/repositories/{repository}/branches'
            create_branch_payload = {'name': branch, 'source': 'main'}

            create_branch_response = requests.post(create_branch_url, headers={
                'Authorization': f'Basic {self.auth_header}',
                'Content-Type': 'application/json'
            }, data=json.dumps(create_branch_payload))

            if create_branch_response.status_code == 201:
                logger.info(f'Branch created successfully: {branch}')
            else:
                logger.error(f'Failed to create branch: {create_branch_response.text}')
                return False
            
        elif branch_response.status_code == 200:
            pass
        
        else:
            logger.error(f'Error checking branch: {branch_response.text}')
            return False
        
        return True

    def get_auth_header(self):  
        auth_string = f'{self.lakefs_access_key}:{self.lakefs_secret_key}'
        return base64.b64encode(auth_string.encode()).decode()
    
    