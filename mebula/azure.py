import contextlib
import unittest.mock
from collections import defaultdict
from typing import Dict, List

try:
    import azure.mgmt.compute  # type: ignore
    import msrest  # type: ignore
    from azure.mgmt.compute.v2019_03_01 import models  # type: ignore
    from azure.mgmt.compute.v2019_03_01 import operations
except ImportError:
    raise ImportError(
        "The mebula 'azure' module requires the pip package ``mebula[azure]``"
    )


class AzureState:
    def __init__(self):
        self.instances: Dict[str, List[models.VirtualMachine]] = defaultdict(list)


class MockPoller:
    """
    Like an AzureOperationPoller
    """

    def __init__(self, response):
        self.response = response

    def result(self, timeout=None):
        return self.response


class VirtualMachinesOperations(operations.VirtualMachinesOperations):
    def __init__(self, state: AzureState):
        self.models: Dict[str, msrest.serialization.Model] = {
            k: v for k, v in models.__dict__.items() if isinstance(v, type)
        }
        self.state = state

    def create_or_update(
        self,
        resource_group_name: str,
        vm_name: str,
        parameters,
        custom_headers=None,
        raw=False,
        polling=True,
        **operation_config
    ):
        vm = self.models["VirtualMachine"].from_dict(parameters)
        vm.name = vm_name

        self.state.instances[resource_group_name].append(vm)

        return MockPoller(vm)

    def get(
        self,
        resource_group_name,
        vm_name,
        expand=None,
        custom_headers=None,
        raw=False,
        **operation_config
    ):
        vm = [
            i for i in self.state.instances[resource_group_name] if i.name == vm_name
        ][0]
        return MockPoller(vm)

    def list(
        self, resource_group_name, custom_headers=None, raw=False, **operation_config
    ):
        return (i for i in self.state.instances[resource_group_name])


@contextlib.contextmanager
def mock_azure():
    state = AzureState()

    with unittest.mock.patch.object(
        azure.mgmt.compute.ComputeManagementClient,
        "virtual_machines",
        new=VirtualMachinesOperations(state),
    ):
        yield
