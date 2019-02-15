# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END

""" Test end to end flow with:
        Playback south plugin
        Delta, RMS, Rate, Scale, Asset & Metadata filter plugins
        PI Server (C) plugin
"""


import http.client
import os
import json
import time
import pytest


__author__ = "Vaibhav Singhal"
__copyright__ = "Copyright (c) 2019 Dianomic Systems"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"


SOUTH_PLUGIN = "Expression"
SOUTH_PLUGIN_LANGUAGE = "C"

SVC_NAME = "playfilter"
ASSET_NAME = "Expression"


CSV_NAME = "sample.csv"
CSV_HEADERS = "ivalue"
CSV_DATA = [{'ivalue': 10},
            {'ivalue': 20},
            {'ivalue': 30}]

NORTH_TASK_NAME = "NorthReadingsTo_PI"

_data_str = {}


class TestE2eCsvMultiFltrPi:

    @pytest.fixture
    def start_south_north(self, reset_and_start_foglamp, add_south, enable_schedule, remove_directories,
                          south_branch, foglamp_url, add_filter, filter_branch, filter_name,
                          start_north_pi_server_c, pi_host, pi_port, pi_token, asset_name="e2e_csv_filter_pi"):
        """ This fixture clone a south and north repo and starts both south and north instance

            reset_and_start_foglamp: Fixture that resets and starts foglamp, no explicit invocation, called at start
            add_south: Fixture that adds a south service with given configuration with enabled or disabled mode
            remove_directories: Fixture that remove directories created during the tests
        """

        # Define configuration of foglamp south playback service
        south_config = {"assetName": {"value": "{}".format(asset_name)},
                        "csvFilename": {"value": "{}".format(CSV_NAME)},
                        "ingestMode": {"value": "batch"}}

        # Define the CSV data and create expected lists to be verified later
        csv_file_path = os.path.join(os.path.expandvars('${FOGLAMP_ROOT}'), 'data/{}'.format(CSV_NAME))
        f = open(csv_file_path, "w")
        f.write(CSV_HEADERS)
        _heads = CSV_HEADERS.split(",")
        for c_data in CSV_DATA:
            temp_data = []
            for _head in _heads:
                temp_data.append(str(c_data[_head]))
            row = ','.join(temp_data)
            f.write("\n{}".format(row))
        f.close()

        # Prepare list of values for each header
        for _head in _heads:
            tmp_list = []
            for c_data in CSV_DATA:
                tmp_list.append(c_data[_head])
            _data_str[_head] = tmp_list

        south_plugin = "playback"
        add_south(south_plugin, south_branch, foglamp_url, service_name=SVC_NAME,
                  config=south_config, start_service=False)

        filter_cfg = {"enable": "true"}
        # I/P 10, 20, 30 -> O/P 1000, 2000, 3000
        add_filter("scale", filter_branch, "fscale", filter_cfg, foglamp_url, SVC_NAME)

        # "asset_name": "e2e_csv_filter_pi", "action": "rename", "new_asset_name": "e2e_filters"
        # I/P e2e_csv_filter_pi > O/P e2e_filters
        add_filter("asset", filter_branch, "fasset", filter_cfg, foglamp_url, SVC_NAME)
        add_filter("metadata", filter_branch, "fmeta", filter_cfg, foglamp_url, SVC_NAME)

        enable_schedule(foglamp_url, SVC_NAME)

        # FIXME: FOGL-2417
        # We need to make north PI sending process to handle the case, to send and retrieve applied filter data
        # in running service, so that we don't need to add south service in disabled mode And enable after applying
        # filter pipeline
        start_north_pi_server_c(foglamp_url, pi_host, pi_port, pi_token)

        yield self.start_south_north

        remove_directories("/tmp/foglamp-south-{}".format(SOUTH_PLUGIN.lower()))
        remove_directories("/tmp/foglamp-filter-{}".format("metadata"))

    def test_end_to_end(self, start_south_north, disable_schedule, foglamp_url, read_data_from_pi, pi_host, pi_admin,
                        pi_passwd, pi_db, wait_time, retries):
        """ Test that data is inserted in FogLAMP using expression south plugin & metadata filter, and sent to PI
            start_south_north: Fixture that starts FogLAMP with south service, add filter and north instance
            Assertions:
                on endpoint GET /foglamp/asset
                on endpoint GET /foglamp/asset/<asset_name> with applied data processing filter value
                data received from PI is same as data sent"""

        time.sleep(wait_time)
        conn = http.client.HTTPConnection(foglamp_url)
        # self._verify_ingest(conn)

        # disable schedule to stop the service and sending data
        disable_schedule(foglamp_url, SVC_NAME)

        # self._verify_egress(read_data_from_pi, pi_host, pi_admin, pi_passwd, pi_db, wait_time, retries)

    def _verify_ingest(self, conn):

        conn.request("GET", '/foglamp/asset')
        r = conn.getresponse()
        assert 200 == r.status
        r = r.read().decode()
        jdoc = json.loads(r)
        assert 1 == len(jdoc)
        assert ASSET_NAME == jdoc[0]["assetCode"]
        assert 0 < jdoc[0]["count"]

        conn.request("GET", '/foglamp/asset/{}'.format(ASSET_NAME))
        r = conn.getresponse()
        assert 200 == r.status
        r = r.read().decode()
        jdoc = json.loads(r)
        assert 0 < len(jdoc)

        # read = jdoc[0]["reading"]
        # assert 1.61977519054386 == read["Expression"]
        # # verify filter is applied and we have {name: value} pair added by metadata filter
        # assert "value" == read["name"]

    def _verify_egress(self, read_data_from_pi, pi_host, pi_admin, pi_passwd, pi_db, wait_time, retries):

        retry_count = 0
        data_from_pi = None
        while (data_from_pi is None or data_from_pi == []) and retry_count < retries:
            data_from_pi = read_data_from_pi(pi_host, pi_admin, pi_passwd, pi_db, ASSET_NAME, {"Expression", "name"})
            retry_count += 1
            time.sleep(wait_time * 2)

        if data_from_pi is None or retry_count == retries:
            assert False, "Failed to read data from PI"

        assert len(data_from_pi)
        assert "name" in data_from_pi
        assert "Expression" in data_from_pi
        assert isinstance(data_from_pi["name"], list)
        assert isinstance(data_from_pi["Expression"], list)
        assert "value" in data_from_pi["name"]
        assert 1.61977519054386 in data_from_pi["Expression"]
