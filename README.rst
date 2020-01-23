Mebula
======

Mebula is a framework which you can use in your testing code to mock your calls to cloud providers' APIs.
At the moment, Oracle's OCI, Google Cloud and Microsoft Azure are supported.

Installation
------------

- For Microsoft Azure, install the ``mebula[azure]`` package.
- For Google Cloud, install the ``mebula[google]`` package.
- For Oracle's OCI, install the ``mebula[oracle]`` package.

Usage
-----

You can use the ``mock_google`` context manager and then use the Google API functions as normal:

.. code:: python

    import googleapiclient.discovery
    import pytest

    from mebula import mock_google

    @pytest.fixture(scope="function")
    def client():
        with mock_google():
            yield googleapiclient.discovery.build("compute", "v1")

    def my_test(client):
        assert client.instances().list(project="foo", zone="bar").execute() == {}

Coverage
--------

Coverage is very minimal at the moment. Only launching and listing instances is supported.
