from sync import update_pl_cfg_in_db
from test.helpers import insert, truncate, find_jf_playlist_by_name
from utils.db import PlaylistConfigResp, load_playlist_configs
from utils.jf import load_jf_playlist, create_playlist, find_user_by_name


def test_stage_1_update_pl_cfg_in_db_scenario_1(local_infra, jf_session):
    """Test that playlist configuration is correctly created in the database."""
    # This test would call the function that updates the playlist configuration in the database
    # and then verify that the expected configuration is present in the database.
    # The actual implementation would depend on how the database is structured and how the configuration is stored.
    truncate(PlaylistConfigResp)
    pl_cfg = PlaylistConfigResp(id=None,
                                jf_pl_id=None,
                                jf_pl_name=None,
                                ytm_pl_id='PL8xOIxSY5muApCYDDmUiKZyKMpdNMt-pM',
                                ytm_pl_name='WRONG_NAME',
                                jf_user_name='test',
                                sync=True)
    insert(pl_cfg)
    update_pl_cfg_in_db()
    pl_cfg_upd = load_playlist_configs()[0]
    assert pl_cfg_upd.jf_pl_id is not None, "JF playlist ID should be set in the database"
    assert pl_cfg_upd.jf_pl_name == pl_cfg_upd.ytm_pl_name, "JF playlist name should match the YT playlist name in the database"
    assert pl_cfg_upd.jf_pl_name == 'test_1', "Newly created JF playlist name should match the actual YT playlist name"


def test_stage_1_update_pl_cfg_in_db_scenario_2(local_infra, jf_session):
    """Test that playlist configuration is correctly mapped in the database."""
    # Scenario: JF already has a playlist and configuration matches the YT playlist by id to JF playlist by name
    truncate(PlaylistConfigResp)
    pl_cfg = PlaylistConfigResp(id=None,
                                jf_pl_id=None,
                                jf_pl_name='my_test_playlist',
                                ytm_pl_id='PL8xOIxSY5muApCYDDmUiKZyKMpdNMt-pM',
                                ytm_pl_name='WRONG_NAME',
                                jf_user_name='test',
                                sync=True)
    insert(pl_cfg)
    jf_pl = find_jf_playlist_by_name(pl_cfg.jf_pl_name)
    if jf_pl:
        jf_pl_id = jf_pl['Id']
        print("Found playlist")
    else:
        jf_pl_id = create_playlist(pl_cfg.jf_pl_name, find_user_by_name(pl_cfg.jf_user_name).id)
        print("Created playlist id=" + jf_pl_id)
    update_pl_cfg_in_db()
    cfgs = load_playlist_configs()
    print("Configs: " + str(len(cfgs)))
    pl_cfg_upd = cfgs[0]
    assert pl_cfg_upd.jf_pl_id == jf_pl_id, "JF playlist ID should match the existing JF playlist ID"