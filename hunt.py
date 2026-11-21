#!/usr/bin/env python3
"""Launch one Oracle Always Free Ampere A1 instance from CI.

Always exits 0 so the 10-minute schedule cannot spam failure mail.
Results go to $GITHUB_OUTPUT as: claimed, ip, ad, instance_id, adopted,
ocpus, memory_gb, error, error_detail.
"""

import os
import pathlib
import re
import tempfile
import time

import oci

SHAPE = "VM.Standard.A1.Flex"
DEFAULT_SHAPE_CONFIGS = "1x6,2x12"
NAME = os.environ.get("INSTANCE_NAME", "openbot-vps")
VCN_NAME = "openbot-vcn"
SUBNET_NAME = "openbot-subnet"
BOOT_GB = int(os.environ.get("BOOT_GB", "50"))
WAIT_SECONDS = int(os.environ.get("WAIT_SECONDS", "300"))
ACTIVE = {"RUNNING", "STARTING", "PROVISIONING"}
CAPACITY_MARKERS = ("out of host capacity", "out of capacity", "capacity")


def log(msg):
    print(msg, flush=True)


def out(**kw):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for key, value in kw.items():
                value = str(value)
                if "\n" in value or "\r" in value:
                    delimiter = f"EOF_{os.getpid()}_{time.time_ns()}"
                    fh.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
                else:
                    fh.write(f"{key}={value}\n")
    for key, value in kw.items():
        log(f"{key}={value}")


def parse_shape_configs(value):
    """Parse an ordered comma-separated list such as ``1x6,2x12``."""
    configs = []
    for part in value.split(","):
        match = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*", part)
        if match is None:
            raise ValueError(f"invalid SHAPE_CONFIGS entry: {part!r}; expected OCPUxMEMORY_GB")
        ocpus, memory_gb = int(match.group(1)), float(match.group(2))
        if ocpus < 1 or memory_gb <= 0:
            raise ValueError(f"invalid SHAPE_CONFIGS entry: {part!r}; values must be positive")
        configs.append((ocpus, memory_gb))
    if not configs:
        raise ValueError("SHAPE_CONFIGS must contain at least one OCPUxMEMORY_GB config")
    return configs


def oracle_error_detail(exc):
    headers = getattr(exc, "headers", {}) or {}
    request_id = getattr(exc, "opc_request_id", None) or headers.get("opc-request-id", "")
    message = getattr(exc, "message", None) or str(exc)
    return f"HTTP {getattr(exc, 'status', '')} {getattr(exc, 'code', '')}: {message}; opc-request-id={request_id}"


def make_config():
    key = os.environ["OCI_PRIVATE_KEY"].replace("\r\n", "\n").strip() + "\n"
    path = pathlib.Path(tempfile.mkdtemp()) / "oci_api_key.pem"
    path.write_text(key, encoding="utf-8")
    os.chmod(path, 0o600)
    cfg = {
        "user": os.environ["OCI_USER"].strip(),
        "fingerprint": os.environ["OCI_FINGERPRINT"].strip(),
        "tenancy": os.environ["OCI_TENANCY"].strip(),
        "region": os.environ.get("OCI_REGION", "ap-singapore-1").strip(),
        "key_file": str(path),
    }
    oci.config.validate_config(cfg)
    return cfg


def ssh_key():
    for candidate in ("ssh_key.pub",):
        p = pathlib.Path(__file__).resolve().parent / candidate
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    return os.environ.get("SSH_PUBLIC_KEY", "").strip()


def public_ip(network, compartment, instance_id):
    for attachment in network.list_vnic_attachments(compartment, instance_id=instance_id).data:
        if attachment.lifecycle_state == "ATTACHED":
            vnic = network.get_vnic(attachment.vnic_id).data
            if vnic.public_ip:
                return vnic.public_ip
    return ""


def find_running(compute, compartment):
    for inst in compute.list_instances(compartment, display_name=NAME).data:
        if inst.lifecycle_state in ACTIVE:
            return inst
    return None


def ensure_subnet(network, compartment):
    for subnet in network.list_subnets(compartment).data:
        if subnet.display_name == SUBNET_NAME:
            return subnet.id

    log(f"subnet {SUBNET_NAME} missing; creating VCN {VCN_NAME}")
    vcn = next(
        (v for v in network.list_vcns(compartment).data if v.display_name == VCN_NAME), None
    )
    if vcn is None:
        vcn = network.create_vcn(
            oci.core.models.CreateVcnDetails(
                compartment_id=compartment,
                display_name=VCN_NAME,
                cidr_block="10.0.0.0/16",
            )
        ).data
    vcn = network.get_vcn(vcn.id).data

    igw = next(iter(network.list_internet_gateways(compartment, vcn_id=vcn.id).data), None)
    if igw is None:
        igw = network.create_internet_gateway(
            oci.core.models.CreateInternetGatewayDetails(
                compartment_id=compartment,
                vcn_id=vcn.id,
                display_name="openbot-igw",
                is_enabled=True,
            )
        ).data

    route_table = network.get_route_table(vcn.default_route_table_id).data
    network.update_route_table(
        route_table.id,
        oci.core.models.UpdateRouteTableDetails(
            route_rules=[
                oci.core.models.RouteRule(
                    destination="0.0.0.0/0",
                    destination_type="CIDR_BLOCK",
                    network_entity_id=igw.id,
                )
            ]
        ),
    )

    security_list = network.get_security_list(vcn.default_security_list_id).data
    network.update_security_list(
        security_list.id,
        oci.core.models.UpdateSecurityListDetails(
            ingress_security_rules=[
                oci.core.models.IngressSecurityRule(
                    protocol="6",
                    source="0.0.0.0/0",
                    tcp_options=oci.core.models.TcpOptions(
                        destination_port_range=oci.core.models.PortRange(min=22, max=22)
                    ),
                ),
                oci.core.models.IngressSecurityRule(protocol="1", source="0.0.0.0/0"),
            ],
            egress_security_rules=security_list.egress_security_rules,
        ),
    )

    subnet = network.create_subnet(
        oci.core.models.CreateSubnetDetails(
            compartment_id=compartment,
            vcn_id=vcn.id,
            display_name=SUBNET_NAME,
            cidr_block="10.0.1.0/24",
            route_table_id=route_table.id,
            security_list_ids=[security_list.id],
        )
    ).data
    return subnet.id


def main():
    shape_configs = parse_shape_configs(os.environ.get("SHAPE_CONFIGS", DEFAULT_SHAPE_CONFIGS))
    cfg = make_config()
    tenancy = cfg["tenancy"]
    compartment = os.environ.get("COMPARTMENT") or tenancy
    identity = oci.identity.IdentityClient(cfg)
    compute = oci.core.ComputeClient(cfg)
    network = oci.core.VirtualNetworkClient(cfg)

    running = find_running(compute, compartment)
    if running is not None:
        ip = public_ip(network, compartment, running.id)
        log(f"instance already {running.lifecycle_state} in {running.availability_domain}")
        running_config = getattr(running, "shape_config", None)
        out(claimed="true", adopted="true", ip=ip, ad=running.availability_domain,
            instance_id=running.id, ocpus=getattr(running_config, "ocpus", ""),
            memory_gb=getattr(running_config, "memory_in_gbs", ""), error="", error_detail="")
        return 0

    ads = [ad.name for ad in identity.list_availability_domains(tenancy).data]
    images = compute.list_images(
        compartment,
        operating_system="Canonical Ubuntu",
        operating_system_version="24.04",
        shape=SHAPE,
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    if not images:
        raise RuntimeError("no Ubuntu 24.04 image for this shape in this region")
    image = images[0]
    subnet_id = ensure_subnet(network, compartment)
    key = ssh_key()
    if not key:
        raise RuntimeError("ssh_key.pub is missing from the repo")

    attempts = []
    launch_errors = []
    instance = None
    accepted_config = None
    accepted_ad = None
    for ad in ads:
        for ocpus, memory_gb in shape_configs:
            for retry in range(2):
                try:
                    details = oci.core.models.LaunchInstanceDetails(
                        compartment_id=compartment,
                        availability_domain=ad,
                        display_name=NAME,
                        shape=SHAPE,
                        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                            ocpus=ocpus, memory_in_gbs=memory_gb
                        ),
                        source_details=oci.core.models.InstanceSourceViaImageDetails(
                            image_id=image.id, boot_volume_size_in_gbs=BOOT_GB
                        ),
                        create_vnic_details=oci.core.models.CreateVnicDetails(
                            subnet_id=subnet_id, assign_public_ip=True
                        ),
                        metadata={"ssh_authorized_keys": key},
                    )
                    instance = compute.launch_instance(details).data
                    accepted_config = (ocpus, memory_gb)
                    accepted_ad = ad
                    log(f"launch accepted in {ad} with {ocpus} OCPU/{memory_gb:g} GB: {instance.id}")
                    break
                except oci.exceptions.ServiceError as exc:
                    detail = oracle_error_detail(exc)
                    log(f"launch failed in {ad} with {ocpus} OCPU/{memory_gb:g} GB: {detail}")
                    if getattr(exc, "status", 0) == 429:
                        if retry == 0:
                            log(f"{ad} {ocpus}x{memory_gb:g}: rate limited; retrying once in 5 seconds")
                            time.sleep(5)
                            continue
                        attempts.append(f"{ad} {ocpus}x{memory_gb:g}: rate limited after retry: {detail}")
                        launch_errors.append(f"rate limited after retry: {detail}")
                        break
                    text = f"{getattr(exc, 'message', '')} {getattr(exc, 'code', '')}".lower()
                    if any(m in text for m in CAPACITY_MARKERS):
                        attempts.append(f"{ad} {ocpus}x{memory_gb:g}: {detail}")
                        break
                    raise
            if instance is not None:
                break
        if instance is not None:
            break

    if instance is None:
        detail = "; ".join(attempts)
        log("no launch accepted: " + (detail or "no availability domains or candidates"))
        out(claimed="false", adopted="false", ip="", ad="", instance_id="",
            ocpus="", memory_gb="", error="; ".join(launch_errors), error_detail=detail)
        return 0

    ad = accepted_ad
    ocpus, memory_gb = accepted_config
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        current = compute.get_instance(instance.id).data
        if current.lifecycle_state == "RUNNING":
            ip = public_ip(network, compartment, instance.id)
            out(claimed="true", adopted="false", ip=ip, ad=ad, instance_id=instance.id,
                ocpus=ocpus, memory_gb=memory_gb, error="", error_detail="")
            return 0
        if current.lifecycle_state in ("TERMINATED", "TERMINATING"):
            raise RuntimeError("instance terminated during provisioning")
        time.sleep(6)
    out(claimed="true", adopted="false", ip="", ad=ad, instance_id=instance.id,
        ocpus=ocpus, memory_gb=memory_gb, error="", error_detail="instance did not reach RUNNING before timeout")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        log(f"ERROR {type(exc).__name__}: {exc}")
        detail = oracle_error_detail(exc) if isinstance(exc, oci.exceptions.ServiceError) else f"{type(exc).__name__}: {exc}"
        out(claimed="false", adopted="false", ip="", ad="", instance_id="", ocpus="",
            memory_gb="", error=detail, error_detail=detail)
        raise SystemExit(0)
