import re
import time
from urllib.parse import urlsplit

import kfp
import requests
from kubernetes.client.models import (
    V1ConfigMapEnvSource,
    V1EmptyDirVolumeSource,
    V1EnvFromSource,
    V1NFSVolumeSource,
    V1Volume,
    V1VolumeMount,
)


class KubeflowClient:
    def __init__(self, endpoint, username, password, namespace) -> None:
        auth_session = get_istio_auth_session(url=endpoint, username=username, password=password)

        self.client = kfp.Client(
            host=f"{endpoint}/pipeline",
            cookies=auth_session["session_cookie"],
            namespace=namespace,
        )

    def upload_pipeline(self, pipeline_pkg_path, pipeline_name):
        pid = self.client.get_pipeline_id(pipeline_name)
        if pid is None:
            return self.client.upload_pipeline(pipeline_pkg_path, pipeline_name)

        pipeline_version_name = f"{pipeline_name}-{time.strftime('%Y-%m-%d %I:%M:%S')}"
        return self.client.upload_pipeline_version(
            pipeline_package_path=pipeline_pkg_path,
            pipeline_version_name=pipeline_version_name,
            pipeline_name=pipeline_name,
        )

@staticmethod
def get_istio_auth_session(url: str, username: str, password: str) -> dict:
    """
    Determine if the specified URL is secured by Dex and try to obtain a session cookie.
    WARNING: only Dex `staticPasswords` and `LDAP` authentication are currently supported
             (we default default to using `staticPasswords` if both are enabled)

    :param url: Kubeflow server URL, including protocol
    :param username: Dex `staticPasswords` or `LDAP` username
    :param password: Dex `staticPasswords` or `LDAP` password
    :return: auth session information
    """
    # define the default return object
    auth_session = {
        "endpoint_url": url,  # KF endpoint URL
        "redirect_url": None,  # KF redirect URL, if applicable
        "dex_login_url": None,  # Dex login URL (for POST of credentials)
        "is_secured": None,  # True if KF endpoint is secured
        "session_cookie": None,  # Resulting session cookies in the form "key1=value1; key2=value2"
    }

    # use a persistent session (for cookies)
    with requests.Session() as s:

        ################
        # Determine if Endpoint is Secured
        ################
        resp = s.get(url, allow_redirects=True)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP status code '{resp.status_code}' for GET against: {url}")

        auth_session["redirect_url"] = resp.url

        # if we were NOT redirected, then the endpoint is UNSECURED
        if len(resp.history) == 0:
            auth_session["is_secured"] = False
            return auth_session
        else:
            auth_session["is_secured"] = True

        ################
        # Get Dex Login URL
        ################
        redirect_url_obj = urlsplit(auth_session["redirect_url"])

        # if we are at `/auth?=xxxx` path, we need to select an auth type
        if re.search(r"/auth$", redirect_url_obj.path):

            #######
            # TIP: choose the default auth type by including ONE of the following
            #######

            # OPTION 1: set "staticPasswords" as default auth type
            redirect_url_obj = redirect_url_obj._replace(
                path=re.sub(r"/auth$", "/auth/local", redirect_url_obj.path)
            )
            # OPTION 2: set "ldap" as default auth type
            # redirect_url_obj = redirect_url_obj._replace(
            #     path=re.sub(r"/auth$", "/auth/ldap", redirect_url_obj.path)
            # )

        # if we are at `/auth/xxxx/login` path, then no further action is needed (we can use it for login POST)
        if re.search(r"/auth/.*/login$", redirect_url_obj.path):
            auth_session["dex_login_url"] = redirect_url_obj.geturl()

        # else, we need to be redirected to the actual login page
        else:
            # this GET should redirect us to the `/auth/xxxx/login` path
            resp = s.get(redirect_url_obj.geturl(), allow_redirects=True)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"HTTP status code '{resp.status_code}' for GET against: {redirect_url_obj.geturl()}"
                )

            # set the login url
            auth_session["dex_login_url"] = resp.url

        ################
        # Attempt Dex Login
        ################
        resp = s.post(
            auth_session["dex_login_url"], data={"login": username, "password": password}, allow_redirects=True
        )
        if len(resp.history) == 0:
            raise RuntimeError(
                f"Login credentials were probably invalid - "
                f"No redirect after POST to: {auth_session['dex_login_url']}"
            )

        # store the session cookies in a "key1=value1; key2=value2" string
        auth_session["session_cookie"] = "; ".join([f"{c.name}={c.value}" for c in s.cookies])

    return auth_session


def add_sharedmemory(container_op):
    shmdir_volume = V1Volume(
        name="shmdir",
        empty_dir=V1EmptyDirVolumeSource(medium="Memory", size_limit="512M"),
    )
    container_op.add_volume(shmdir_volume)
    container_op.add_volume_mount(V1VolumeMount(mount_path="/dev/shm", name="shmdir"))  # shared memory


def add_nfs_volume(container_op, volume_name, nfs_server, nfs_path, mount_path):
    nfs_volume = V1Volume(
        name=volume_name,
        nfs=V1NFSVolumeSource(server=nfs_server, path=nfs_path),
    )
    container_op.add_volume(nfs_volume)
    container_op.add_volume_mount(V1VolumeMount(mount_path=mount_path, name=volume_name))


def add_configmap(container_op, configmap_name):
    env_from_source = V1EnvFromSource(config_map_ref=V1ConfigMapEnvSource(name=configmap_name))
    container_op.add_env_from(env_from_source)


