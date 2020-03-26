# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT

import oci  # type: ignore

from mebula.oracle import mock_oracle


def test_oracle_empty():
    with mock_oracle():
        compute = oci.core.ComputeClient(config={})
        assert compute.list_instances("foo").data == []


def test_oracle_one_round_trip():
    with mock_oracle():
        compute = oci.core.ComputeClient(config={})
        instance_details = oci.core.models.LaunchInstanceDetails(
            compartment_id="compartment_id", display_name="foo",
        )
        compute.launch_instance(instance_details)

        instances = compute.list_instances("compartment_id").data
        assert len(instances) == 1
        assert instances[0].display_name == "foo"
