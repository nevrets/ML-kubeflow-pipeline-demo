import argparse
import datetime
import glob
import os
from pathlib import Path
import pytz
from loguru import logger

import lakefs_client
from lakefs_client import models
from lakefs_client.client import LakeFSClient
from lakefs import LakeFS

LAKEFS_ACCESS_KEY_ID = os.environ["LAKEFS_ACCESS_KEY_ID"]
LAKEFS_SECRET_ACCESS_KEY = os.environ["LAKEFS_SECRET_ACCESS_KEY"]
LAKEFS_URL = os.environ["LAKEFS_URL"]



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", help="upload path")
    parser.add_argument("--repo", help="lakefs repository")
    parser.add_argument("--branch", help="lakefs branch")
    args = parser.parse_args()

    # Setting Lakefs Config
    configuration = lakefs_client.Configuration()
    configuration.username = LAKEFS_ACCESS_KEY_ID
    configuration.password = LAKEFS_SECRET_ACCESS_KEY
    configuration.host = LAKEFS_URL

    # LakeFS 인스턴스 생성
    lakefs = LakeFS()
    
    # Check and create branch
    lakefs.create_lakefs_repository(args.repo)
    lakefs.check_and_create_branch(args.repo, args.branch)

    # LakeFS 클라이언트 생성
    client = LakeFSClient(configuration)

    file_lists = glob.glob(f"{args.root}/**/*.*", recursive=True)
    kst = pytz.timezone('Asia/Seoul')
    today_h_dir = datetime.datetime.now(tz=kst).strftime("%Y-%m-%d-%H%M%S")
    logger.info(f"Uploading files to LakeFS at {today_h_dir}")

    for file in file_lists:
        with open(os.path.join(args.root, file), "rb") as f:
            logger.info(f"{file} upload...")
            path = Path(file)
            lakefs_path = os.path.join(today_h_dir, path.parent.name, path.name)

            client.objects.upload_object(repository=args.repo, branch=args.branch, path=lakefs_path, content=f)

    # Lakefs Commits
    client.commits.commit(
        repository=args.repo,
        branch=args.branch,
        commit_creation=models.CommitCreation(
            message=f"{today_h_dir} Upload files!",
            metadata={},
        ),
    )
    logger.info(f'Commit done..."{today_h_dir} Upload files!"')
