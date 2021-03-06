"""
Copyright 2020 The Magma Authors.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import unittest
from concurrent.futures import Future
from unittest.mock import MagicMock

import warnings
from lte.protos.mconfig.mconfigs_pb2 import PipelineD
from lte.protos.policydb_pb2 import FlowDescription, FlowMatch, PolicyRule, \
    RedirectInformation
from lte.protos.pipelined_pb2 import ActivateFlowsRequest, SetupFlowsRequest
from magma.subscriberdb.sid import SIDUtils
from magma.pipelined.app.enforcement import EnforcementController
from magma.pipelined.app.enforcement_stats import EnforcementStatsController
from magma.pipelined.bridge_util import BridgeTools
from magma.pipelined.app.base import global_epoch
from magma.pipelined.policy_converters import flow_match_to_magma_match, \
    convert_ipv4_str_to_ip_proto
from magma.pipelined.tests.app.packet_builder import IPPacketBuilder, \
    TCPPacketBuilder
from magma.pipelined.tests.app.packet_injector import ScapyPacketInjector
from magma.pipelined.tests.app.start_pipelined import PipelinedController, \
    TestSetup
from magma.pipelined.tests.app.subscriber import RyuDirectSubscriberContext, default_ambr_config
from magma.pipelined.tests.app.table_isolation import RyuDirectTableIsolator, \
    RyuForwardFlowArgsBuilder
from magma.pipelined.tests.pipelined_test_util import fake_controller_setup, \
    create_service_manager, start_ryu_app_thread, stop_ryu_app_thread, \
    wait_after_send, SnapshotVerifier, get_enforcement_stats, \
    wait_for_enforcement_stats
from scapy.all import IP


class RestartResilienceTest(unittest.TestCase):
    BRIDGE = 'testing_br'
    IFACE = 'testing_br'
    MAC_DEST = "5e:cc:cc:b1:49:4b"
    BRIDGE_IP_ADDRESS = '192.168.128.1'
    DEFAULT_DROP_FLOW_NAME = '(??????_???)???????????????'

    def _wait_func(self, stat_names):
        def func():
            wait_after_send(self.testing_controller)
            wait_for_enforcement_stats(self.enforcement_stats_controller,
                                       stat_names)
        return func

    @classmethod
    def setUpClass(cls):
        """
        Starts the thread which launches ryu apps

        Create a testing bridge, add a port, setup the port interfaces. Then
        launch the ryu apps for testing pipelined. Gets the references
        to apps launched by using futures, mocks the redis policy_dictionary
        of enforcement_controller
        """
        super(RestartResilienceTest, cls).setUpClass()
        warnings.simplefilter('ignore')
        cls._static_rule_dict = {}
        cls.service_manager = create_service_manager([PipelineD.ENFORCEMENT])
        cls._enforcement_tbl_num = cls.service_manager.get_table_num(
            EnforcementController.APP_NAME)
        cls._tbl_num = cls.service_manager.get_table_num(
            EnforcementController.APP_NAME)

        enforcement_controller_reference = Future()
        testing_controller_reference = Future()
        enf_stat_ref = Future()
        startup_flows_ref = Future()

        def mock_thread_safe(cmd, body):
            cmd(body)
        loop_mock = MagicMock()
        loop_mock.call_soon_threadsafe = mock_thread_safe

        test_setup = TestSetup(
            apps=[PipelinedController.Enforcement,
                  PipelinedController.Testing,
                  PipelinedController.Enforcement_stats,
                  PipelinedController.StartupFlows],
            references={
                PipelinedController.Enforcement:
                    enforcement_controller_reference,
                PipelinedController.Testing:
                    testing_controller_reference,
                PipelinedController.Enforcement_stats:
                    enf_stat_ref,
                PipelinedController.StartupFlows:
                    startup_flows_ref,
            },
            config={
                'bridge_name': cls.BRIDGE,
                'bridge_ip_address': cls.BRIDGE_IP_ADDRESS,
                'enforcement': {
                    'poll_interval': 2,
                    'default_drop_flow_name': cls.DEFAULT_DROP_FLOW_NAME
                },
                'nat_iface': 'eth2',
                'enodeb_iface': 'eth1',
                'qos': {'enable': False},
                'clean_restart': False,
            },
            mconfig=PipelineD(),
            loop=loop_mock,
            service_manager=cls.service_manager,
            integ_test=False,
            rpc_stubs={'sessiond': MagicMock()}
        )

        BridgeTools.create_bridge(cls.BRIDGE, cls.IFACE)

        cls.thread = start_ryu_app_thread(test_setup)

        cls.enforcement_controller = enforcement_controller_reference.result()
        cls.enforcement_stats_controller = enf_stat_ref.result()
        cls.startup_flows_contoller = startup_flows_ref.result()
        cls.testing_controller = testing_controller_reference.result()

        cls.enforcement_stats_controller._policy_dict = cls._static_rule_dict
        cls.enforcement_stats_controller._report_usage = MagicMock()

        cls.enforcement_controller._policy_dict = cls._static_rule_dict
        cls.enforcement_controller._redirect_manager._save_redirect_entry =\
            MagicMock()

    @classmethod
    def tearDownClass(cls):
        stop_ryu_app_thread(cls.thread)
        BridgeTools.destroy_bridge(cls.BRIDGE)

    def test_enforcement_restart(self):
        """
        Adds rules using the setup feature

        1) Empty SetupFlowsRequest
            - assert default flows
        2) Add 2 imsis, add 2 policies(sub1_rule_temp, sub2_rule_keep),
            - assert everything is properly added
        3) Same imsis 1 new policy, 1 old (sub2_new_rule, sub2_rule_keep)
            - assert everything is properly added
        4) Empty SetupFlowsRequest
            - assert default flows
        """
        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller)
        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'default_flows')
        with snapshot_verifier:
            pass

        imsi1 = 'IMSI010000000088888'
        imsi2 = 'IMSI010000000012345'
        sub2_ip = '192.168.128.74'
        flow_list1 = [
            FlowDescription(
                match=FlowMatch(
                    ip_dst=convert_ipv4_str_to_ip_proto('45.10.0.0/24'),
                    direction=FlowMatch.UPLINK),
                action=FlowDescription.PERMIT),
            FlowDescription(
                match=FlowMatch(
                    ip_dst=convert_ipv4_str_to_ip_proto('45.11.0.0/24'),
                    direction=FlowMatch.UPLINK),
                action=FlowDescription.PERMIT)
        ]
        flow_list2 = [FlowDescription(
            match=FlowMatch(
                ip_dst=convert_ipv4_str_to_ip_proto('10.10.1.0/24'),
                direction=FlowMatch.UPLINK),
            action=FlowDescription.PERMIT)
        ]
        policies1 = [
            PolicyRule(id='sub1_rule_temp', priority=2, flow_list=flow_list1),
        ]
        policies2 = [
            PolicyRule(id='sub2_rule_keep', priority=3, flow_list=flow_list2)
        ]
        enf_stat_name = [imsi1 + '|sub1_rule_temp' + '|' + sub2_ip,
                         imsi2 + '|sub2_rule_keep' + '|' + sub2_ip]

        self.service_manager.session_rule_version_mapper.update_version(
            imsi1, convert_ipv4_str_to_ip_proto(sub2_ip), 'sub1_rule_temp')
        self.service_manager.session_rule_version_mapper.update_version(
            imsi2, convert_ipv4_str_to_ip_proto(sub2_ip), 'sub2_rule_keep')

        setup_flows_request = SetupFlowsRequest(
            requests=[
                ActivateFlowsRequest(
                    sid=SIDUtils.to_pb(imsi1),
                    ip_addr=sub2_ip,
                    dynamic_rules=policies1
                ),
                ActivateFlowsRequest(
                    sid=SIDUtils.to_pb(imsi2),
                    ip_addr=sub2_ip,
                    dynamic_rules=policies2
                ),
            ],
            epoch=global_epoch
        )

        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller,
            setup_flows_request=setup_flows_request)
        sub_context = RyuDirectSubscriberContext(
            imsi2, sub2_ip, self.enforcement_controller,
            self._enforcement_tbl_num
        )
        isolator = RyuDirectTableIsolator(
            RyuForwardFlowArgsBuilder.from_subscriber(sub_context.cfg)
                                     .build_requests(),
            self.testing_controller
        )
        pkt_sender = ScapyPacketInjector(self.IFACE)
        packets = IPPacketBuilder()\
            .set_ip_layer('10.10.1.8/20', sub2_ip)\
            .set_ether_layer(self.MAC_DEST, "00:00:00:00:00:00")\
            .build()
        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'before_restart')
        with isolator, snapshot_verifier:
            pkt_sender.send(packets)

        flow_list1 = [FlowDescription(
            match=FlowMatch(
                ip_dst=convert_ipv4_str_to_ip_proto('24.10.0.0/24'),
                direction=FlowMatch.UPLINK),
            action=FlowDescription.PERMIT)
        ]
        policies = [
            PolicyRule(id='sub2_new_rule', priority=2, flow_list=flow_list1),
            PolicyRule(id='sub2_rule_keep', priority=3, flow_list=flow_list2)
        ]
        self.service_manager.session_rule_version_mapper.update_version(
            imsi2, convert_ipv4_str_to_ip_proto(sub2_ip), 'sub2_new_rule')
        enf_stat_name = [imsi2 + '|sub2_new_rule' + '|' + sub2_ip,
                         imsi2 + '|sub2_rule_keep' + '|' + sub2_ip]
        setup_flows_request = SetupFlowsRequest(
            requests=[ActivateFlowsRequest(
                sid=SIDUtils.to_pb(imsi2),
                ip_addr=sub2_ip,
                dynamic_rules=policies
            )],
            epoch=global_epoch
        )

        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller,
            setup_flows_request=setup_flows_request)
        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'after_restart')
        with snapshot_verifier:
            pass

        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller)
        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'default_flows_w_packets')

        with snapshot_verifier:
            pass

    def test_enforcement_stats_restart(self):
        """
        Adds 2 policies to subscriber, verifies that EnforcementStatsController
        reports correct stats to sessiond

        Assert:
            UPLINK policy matches 128 packets (*34 = 4352 bytes)
            DOWNLINK policy matches 256 packets (*34 = 8704 bytes)
            No other stats are reported

        The controller is then restarted with the same SetupFlowsRequest,
            - assert flows keep their packet counts
        """
        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller)
        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'default_flows')
        with snapshot_verifier:
            pass

        imsi = 'IMSI001010000000013'
        sub_ip = '192.168.128.74'
        num_pkts_tx_match = 128
        num_pkts_rx_match = 256

        """ Create 2 policy rules for the subscriber """
        flow_list1 = [FlowDescription(
            match=FlowMatch(
                ip_dst=convert_ipv4_str_to_ip_proto('45.10.0.0/25'),
        direction=FlowMatch.UPLINK),
            action=FlowDescription.PERMIT)
        ]
        flow_list2 = [FlowDescription(
            match=FlowMatch(
                ip_src=convert_ipv4_str_to_ip_proto('45.10.0.0/24'),
        direction=FlowMatch.DOWNLINK),
            action=FlowDescription.PERMIT)
        ]
        policies = [
            PolicyRule(id='tx_match', priority=3, flow_list=flow_list1),
            PolicyRule(id='rx_match', priority=5, flow_list=flow_list2)
        ]
        enf_stat_name = [imsi + '|tx_match' + '|' + sub_ip,
                         imsi + '|rx_match' + '|' + sub_ip]
        self.service_manager.session_rule_version_mapper.update_version(
            imsi, convert_ipv4_str_to_ip_proto(sub_ip), 'tx_match')
        self.service_manager.session_rule_version_mapper.update_version(
            imsi, convert_ipv4_str_to_ip_proto(sub_ip), 'rx_match')

        """ Setup subscriber, setup table_isolation to fwd pkts """
        self._static_rule_dict[policies[0].id] = policies[0]
        self._static_rule_dict[policies[1].id] = policies[1]
        sub_context = RyuDirectSubscriberContext(
            imsi, sub_ip, self.enforcement_controller,
            self._enforcement_tbl_num, self.enforcement_stats_controller,
            nuke_flows_on_exit=False
        ).add_static_rule(policies[0].id).add_static_rule(policies[1].id)
        isolator = RyuDirectTableIsolator(
            RyuForwardFlowArgsBuilder.from_subscriber(sub_context.cfg)
                                     .build_requests(),
            self.testing_controller
        )

        """ Create 2 sets of packets, for policry rule1&2 """
        pkt_sender = ScapyPacketInjector(self.IFACE)
        packet1 = IPPacketBuilder()\
            .set_ip_layer('45.10.0.0/20', sub_ip)\
            .set_ether_layer(self.MAC_DEST, "00:00:00:00:00:00")\
            .build()
        packet2 = IPPacketBuilder()\
            .set_ip_layer(sub_ip, '45.10.0.0/20')\
            .set_ether_layer(self.MAC_DEST, "00:00:00:00:00:00")\
            .build()

        # =========================== Verification ===========================
        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'initial_flows')
        """ Send packets, wait until pkts are received by ovs and enf stats """
        with isolator, sub_context, snapshot_verifier:
            pkt_sender.send(packet1)
            pkt_sender.send(packet2)

        stats = get_enforcement_stats(
            self.enforcement_stats_controller._report_usage.call_args_list)

        self.assertEqual(stats[enf_stat_name[0]].sid, imsi)
        self.assertEqual(stats[enf_stat_name[0]].rule_id, "tx_match")
        self.assertEqual(stats[enf_stat_name[0]].bytes_rx, 0)
        self.assertEqual(stats[enf_stat_name[0]].bytes_tx,
                         num_pkts_tx_match * len(packet1))
        self.assertEqual(stats[enf_stat_name[1]].sid, imsi)
        self.assertEqual(stats[enf_stat_name[1]].rule_id, "rx_match")
        self.assertEqual(stats[enf_stat_name[1]].bytes_tx, 0)

        # downlink packets will discount ethernet header by default
        # so, only count the IP portion
        total_bytes_pkt2 = num_pkts_rx_match * len(packet2[IP])
        self.assertEqual(stats[enf_stat_name[1]].bytes_rx, total_bytes_pkt2)

        # NOTE this value is 8 because the EnforcementStatsController rule
        # reporting doesn't reset on clearing flows(lingers from old tests)
        self.assertEqual(len(stats), 8)

        setup_flows_request = SetupFlowsRequest(
            requests=[
                ActivateFlowsRequest(
                    sid=SIDUtils.to_pb(imsi),
                    ip_addr=sub_ip,
                    rule_ids=[policies[0].id, policies[1].id]
                ),
            ],
            epoch=global_epoch
        )

        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller,
            setup_flows_request=setup_flows_request)

        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'after_restart')

        with snapshot_verifier:
            pass

        self.assertEqual(stats[enf_stat_name[0]].bytes_tx,
                         num_pkts_tx_match * len(packet1))

    def test_url_redirect(self):
        """
        Partial redirection test, checks if flows were added properly for url
        based redirection.

        Assert:
            1 Packet is matched
            Packet bypass flows are added
            Flow learn action is triggered - another flow is added to the table
        """
        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller)
        redirect_ips = ["185.128.101.5", "185.128.121.4"]
        self.enforcement_controller._redirect_manager._dns_cache.get(
            "about.sha.ddih.org", lambda: redirect_ips, max_age=42
        )
        imsi = 'IMSI010000000088888'
        sub_ip = '192.168.128.74'
        flow_list = [FlowDescription(match=FlowMatch())]
        policy = PolicyRule(
            id='redir_test', priority=3, flow_list=flow_list,
            redirect=RedirectInformation(
                support=1,
                address_type=2,
                server_address="http://about.sha.ddih.org/"
            )
        )

        # ============================ Subscriber ============================
        sub_context = RyuDirectSubscriberContext(
            imsi, sub_ip, self.enforcement_controller, self._tbl_num
        )

        setup_flows_request = SetupFlowsRequest(
            requests=[
                ActivateFlowsRequest(
                    sid=SIDUtils.to_pb(imsi),
                    ip_addr=sub_ip,
                    dynamic_rules=[policy]
                ),
            ],
            epoch=global_epoch
        )

        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller,
            setup_flows_request=setup_flows_request)

        isolator = RyuDirectTableIsolator(
            RyuForwardFlowArgsBuilder.from_subscriber(sub_context.cfg)
                                     .build_requests(),
            self.testing_controller
        )
        pkt_sender = ScapyPacketInjector(self.IFACE)
        packet = TCPPacketBuilder()\
            .set_tcp_layer(42132, 80, 321)\
            .set_tcp_flags("S")\
            .set_ip_layer('151.42.41.122', sub_ip)\
            .set_ether_layer(self.MAC_DEST, "00:00:00:00:00:00")\
            .build()

        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager)

        with isolator, sub_context, snapshot_verifier:
            pkt_sender.send(packet)

    def test_clean_restart(self):
        """
        Use the clean restart flag, verify only default flows are present
        """
        # TODO test that adding a rule when controller isn't init fails.
        self.enforcement_controller._clean_restart = True
        self.enforcement_stats_controller._clean_restart = True

        fake_controller_setup(
            enf_controller=self.enforcement_controller,
            enf_stats_controller=self.enforcement_stats_controller,
            startup_flow_controller=self.startup_flows_contoller)
        snapshot_verifier = SnapshotVerifier(self, self.BRIDGE,
                                             self.service_manager,
                                             'default_flows')
        with snapshot_verifier:
            pass

        self.enforcement_controller._clean_restart = False
        self.enforcement_stats_controller._clean_restart = False


if __name__ == "__main__":
    unittest.main()
