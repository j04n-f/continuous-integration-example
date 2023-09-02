import filecmp
import logging
import subprocess
import tempfile
from pathlib import Path
from time import sleep

import docker
from kubernetes import client
from kubernetes import config
from kubernetes.client.exceptions import ApiException
from python_hosts import Hosts
from python_hosts import HostsEntry

logging.basicConfig(level=logging.INFO, format="%(message)s")


def setup_hosts() -> None:
    entries = []

    net_api = client.NetworkingV1Api()

    ingresses = net_api.list_ingress_for_all_namespaces().items

    for ingress in ingresses:
        ip = ingress.status.load_balancer.ingress[0].ip
        host = ingress.spec.rules[0].host
        entries.append(
            HostsEntry(
                address=ip,
                names=[host],
                entry_type="ipv4",
                comment=f"evp CLI: kubectl get ingress/{ingress.metadata.name}",
            )
        )

    core_api = client.CoreV1Api()
    services = core_api.list_service_for_all_namespaces().items

    for service in services:
        if service.spec.type == "LoadBalancer":
            ip = service.status.load_balancer.ingress[0].ip
            name = service.metadata.name
            namespace = service.metadata.namespace
            host = f"{name}.{namespace}.local"
            entries.append(
                HostsEntry(
                    address=ip,
                    names=[host],
                    entry_type="ipv4",
                    comment=f"evp CLI: kubectl get service/{service.metadata.name}",
                )
            )

    hosts = Hosts()

    for entry in entries:
        hosts.remove_all_matching(address=entry.address)

        for host in entry.names:
            hosts.remove_all_matching(name=host)

    hosts.add(entries=entries)

    with tempfile.NamedTemporaryFile() as tmp:
        tmp_path = Path(tmp.name)
        hosts.write(tmp_path)

        if not filecmp.cmp(hosts.path, tmp_path):
            subprocess.check_output(
                [
                    "sudo",
                    "cp",
                    "-f",
                    tmp_path,
                    hosts.path,
                ]
            )


def main() -> None:
    cluster_name = "ci-example"
    image_tag = "dev"
    image_name = "ghcr.io/joan-mido-qa/ci-example"
    kubeconfig = Path.cwd() / "scripts" / "kubeconfig"

    try:
        subprocess.check_output(
            ["kind", "create", "cluster", "--name", cluster_name, "--wait", "5m"], stderr=subprocess.STDOUT
        )

    except subprocess.CalledProcessError as exc:
        if "already exist" not in exc.stdout.decode():
            raise exc

    logging.info("Kind Cluster Created")

    subprocess.check_output(["kind", "export", "kubeconfig", "--name", cluster_name, "--kubeconfig", kubeconfig])

    docker_client = docker.from_env()

    docker_client.images.build(path=str(Path.cwd()), tag=f"{image_name}:{image_tag}")

    logging.info("Docker Image Built")

    subprocess.check_output(["kind", "load", "docker-image", f"{image_name}:{image_tag}", "--name", cluster_name])

    logging.info("Docker Image Loaded to Kind")

    subprocess.check_output(
        [
            "helm",
            "repo",
            "add",
            "metallb",
            "https://metallb.github.io/metallb",
            "--kubeconfig",
            kubeconfig,
        ]
    )

    subprocess.check_output(
        [
            "helm",
            "repo",
            "add",
            "ingress-nginx",
            "https://kubernetes.github.io/ingress-nginx",
            "--kubeconfig",
            kubeconfig,
        ]
    )

    subprocess.check_output(
        [
            "helm",
            "repo",
            "update",
            "--kubeconfig",
            kubeconfig,
        ]
    )

    subprocess.check_output(
        [
            "helm",
            "upgrade",
            "--install",
            "metallb",
            "metallb/metallb",
            "--wait",
            "--timeout",
            "5m",
            "--kubeconfig",
            kubeconfig,
        ]
    )

    logging.info("Dependencies Downloaded")

    config.load_kube_config(config_file=str(kubeconfig))

    k8s_client = client.CustomObjectsApi()

    kind_subnet = str(docker_client.networks.get("kind").attrs["IPAM"]["Config"][0]["Subnet"])

    try:
        k8s_client.create_namespaced_custom_object(
            group="metallb.io",
            version="v1beta1",
            namespace="default",
            plural="ipaddresspools",
            body={
                "apiVersion": "metallb.io/v1beta1",
                "kind": "IPAddressPool",
                "metadata": {"name": "kind-address-pool"},
                "spec": {
                    "addresses": [kind_subnet.replace(".0.0/16", ".255.0/24")],
                },
            },
        )

    except ApiException as exc:
        if not exc.reason == "Conflict":
            raise exc

        k8s_client.patch_namespaced_custom_object(
            group="metallb.io",
            version="v1beta1",
            namespace="default",
            plural="ipaddresspools",
            name="kind-address-pool",
            body={
                "spec": {
                    "addresses": [kind_subnet.replace(".0.0/16", ".255.0/24")],
                },
            },
        )

    try:
        k8s_client.create_namespaced_custom_object(
            group="metallb.io",
            version="v1beta1",
            namespace="default",
            plural="l2advertisements",
            body={
                "apiVersion": "metallb.io/v1beta1",
                "kind": "L2Advertisement",
                "metadata": {"name": "kind-advertisement"},
            },
        )

    except ApiException as exc:
        if not exc.reason == "Conflict":
            raise exc

    logging.info("Dependencies Installed: MetalLB")

    subprocess.check_output(
        [
            "helm",
            "upgrade",
            "--install",
            "ingress-nginx",
            "ingress-nginx/ingress-nginx",
            "--wait",
            "--timeout",
            "5m",
            "--kubeconfig",
            kubeconfig,
        ],
    )

    logging.info("Dependencies Installed: Ingress-Nginx")

    subprocess.check_output(
        [
            "helm",
            "upgrade",
            "--install",
            "ci-example",
            str(Path.cwd() / "charts" / "ci-example"),
            "--wait",
            "--timeout",
            "5m",
            "--set",
            f"image.tag={image_tag}",
            "--set",
            "ingress.enabled=true",
            "--set",
            "ingress.className=nginx",
            "--kubeconfig",
            kubeconfig,
        ],
    )

    logging.info("CI Example Helm Installed")

    attempts = 0

    while attempts != 10:
        try:
            setup_hosts()
            break

        except Exception as exc:
            logging.warning(f"Attempt {attempts} to create Hosts: {exc}")
            attempts += 1
            sleep(5)

    if attempts == 10:
        raise Exception("Could not setup Host")

    logging.info("Hosts Created")


if __name__ == "__main__":
    main()
