#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fbpcp.entity.mpc_instance import MPCParty
from fbpcs.common.entity.pcs_mpc_instance import PCSMPCInstance
from fbpcs.onedocker_binary_config import OneDockerBinaryConfig
from fbpcs.private_computation.entity.infra_config import (
    InfraConfig,
    PrivateComputationGameType,
)
from fbpcs.private_computation.entity.pcs_feature import PCSFeature
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
    PrivateComputationInstanceStatus,
    PrivateComputationRole,
)
from fbpcs.private_computation.entity.product_config import (
    CommonProductConfig,
    PrivateIdDfcaConfig,
    ProductConfig,
)
from fbpcs.private_computation.repository.private_computation_game import GameNames
from fbpcs.private_computation.service.constants import NUM_NEW_SHARDS_PER_FILE
from fbpcs.private_computation.service.private_id_dfca_aggregate_stage_service import (
    PrivateIdDfcaAggregateStageService,
)


class TestPrivateIdDfcaAggregateStageService(IsolatedAsyncioTestCase):
    @patch("fbpcp.service.mpc.MPCService")
    def setUp(self, mock_mpc_svc) -> None:
        self.mock_mpc_svc = mock_mpc_svc
        self.mock_mpc_svc.get_instance = MagicMock(side_effect=Exception())
        self.mock_mpc_svc.create_instance = MagicMock()
        self.run_id = "681ba82c-16d9-11ed-861d-0242ac120002"

        onedocker_binary_config_map = defaultdict(
            lambda: OneDockerBinaryConfig(
                tmp_directory="/test_tmp_directory/",
                binary_version="latest",
                repository_path="test_path/",
            )
        )
        self.stage_svc = PrivateIdDfcaAggregateStageService(
            onedocker_binary_config_map, self.mock_mpc_svc
        )

    async def test_private_id_dfca_aggregate(self) -> None:
        private_computation_instance = self._create_pc_instance()
        mpc_instance = PCSMPCInstance.create_instance(
            instance_id=private_computation_instance.infra_config.instance_id
            + "_private_id_dfca_aggregate",
            game_name=GameNames.PRIVATE_ID_DFCA_AGGREGATION.value,
            mpc_party=MPCParty.CLIENT,
            num_workers=private_computation_instance.infra_config.num_mpc_containers,
        )

        self.mock_mpc_svc.start_instance_async = AsyncMock(return_value=mpc_instance)

        test_server_ips = [
            f"192.0.2.{i}"
            for i in range(private_computation_instance.infra_config.num_mpc_containers)
        ]
        await self.stage_svc.run_async(private_computation_instance, test_server_ips)
        test_game_args = [
            {
                "input_path": f"{private_computation_instance.data_processing_output_path}_combine_{i}",
                "output_path": f"{private_computation_instance.private_id_dfca_aggregate_stage_output_path}_{i}",
                "run_name": private_computation_instance.infra_config.instance_id,
                "log_cost": True,
                "run_id": self.run_id,
                "pc_feature_flags": private_computation_instance.feature_flags,
            }
            for i in range(private_computation_instance.infra_config.num_mpc_containers)
        ]

        self.assertEqual(
            GameNames.PRIVATE_ID_DFCA_AGGREGATION.value,
            self.mock_mpc_svc.create_instance.call_args[1]["game_name"],
        )
        self.assertEqual(
            test_game_args,
            self.mock_mpc_svc.create_instance.call_args[1]["game_args"],
        )

        self.assertEqual(
            mpc_instance, private_computation_instance.infra_config.instances[0]
        )

    def _create_pc_instance(self) -> PrivateComputationInstance:
        infra_config: InfraConfig = InfraConfig(
            instance_id="test_instance_123",
            role=PrivateComputationRole.PARTNER,
            status=PrivateComputationInstanceStatus.COMPUTATION_COMPLETED,
            status_update_ts=1600000000,
            instances=[],
            game_type=PrivateComputationGameType.PRIVATE_ID_DFCA,
            num_pid_containers=2,
            num_mpc_containers=2,
            num_files_per_mpc_container=NUM_NEW_SHARDS_PER_FILE,
            status_updates=[],
            run_id=self.run_id,
            pcs_features={PCSFeature.PCS_DUMMY},
        )
        common: CommonProductConfig = CommonProductConfig(
            input_path="456",
            output_dir="789",
        )
        product_config: ProductConfig = PrivateIdDfcaConfig(
            common=common,
        )
        return PrivateComputationInstance(
            infra_config=infra_config,
            product_config=product_config,
        )