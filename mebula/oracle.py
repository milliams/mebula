import contextlib
import datetime
import functools
import unittest.mock
from collections import defaultdict
from typing import Dict, List

try:
    import oci  # type: ignore
except ImportError:
    raise ImportError(
        "The mebula 'oracle' module requires the pip package ``mebula[oracle]``"
    )


def oracle_arg_check(f):
    """
    A decorator which calls a mocked version of an OCI function to use
    it to check the arguments passed.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        getattr(args[0].client, f.__name__)(unittest.mock.Mock(), *args[1:], **kwargs)
        return f(*args, **kwargs)

    return wrapper


class OracleComputeClient:
    """
    A mocked version of oci.core.ComputeClient
    """

    def __init__(self, config: dict, **kwargs):
        self.client = oci.core.compute_client.ComputeClient
        self._instances: Dict[str, List[oci.core.models.Instance]] = defaultdict(list)

    @oracle_arg_check
    def list_instances(self, compartment_id: str, **kwargs) -> oci.response.Response:
        ins = self._instances[compartment_id]
        filters = {"availability_domain", "display_name", "lifecycle_state"}
        for f in filters:
            if f in kwargs:
                ins = [i for i in ins if getattr(i, f) == kwargs[f]]

        if "sort_by" in kwargs:
            if "sort_order" in kwargs:
                reverse = kwargs["sort_order"] == "DESC"
            else:
                reverse = None
            if kwargs["sort_by"] == "TIMECREATED":
                reverse = reverse if reverse is not None else True
                ins = sorted(ins, key=lambda i: i.time_created, reverse=reverse)
            elif kwargs["sort_by"] == "DISPLAYNAME":
                reverse = reverse if reverse is not None else False
                ins = sorted(ins, key=lambda i: i.display_name, reverse=reverse)

        return oci.response.Response(200, None, ins, None)

    @oracle_arg_check
    def launch_instance(
        self, launch_instance_details: oci.core.models.LaunchInstanceDetails, **kwargs
    ):
        instance = oci.core.models.Instance(
            availability_domain=launch_instance_details.availability_domain,
            display_name=launch_instance_details.display_name,
            freeform_tags=launch_instance_details.freeform_tags,
            lifecycle_state="RUNNING",
            time_created=datetime.datetime.now(),
        )
        self._instances[launch_instance_details.compartment_id].append(instance)


@contextlib.contextmanager
def mock_oracle():
    with unittest.mock.patch("oci.core.ComputeClient", new=OracleComputeClient):
        yield
