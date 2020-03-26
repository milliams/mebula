# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT


def mock_azure():
    from . import azure

    return azure.mock_azure()


def mock_google():
    from . import google

    return google.mock_google()


def mock_oracle():
    from . import oracle

    return oracle.mock_oracle()
