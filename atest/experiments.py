import os
import unittest

import docker

import sync
from sync import sub_videos_with_songs, resolve_video_substitution
from utils import db, jf
from utils.common import get_nested_value
from utils.db import load_settings, load_guser_by_id
from utils.jf import find_user_by_name
from utils.logs import create_logger
from utils.ytm import createYtMusic, Category, refresh_access_token

logger = create_logger("main")


class MyTestCase(unittest.TestCase):
    def test_replace_1_song(self):
        sync.SLACK_CHANNEL_DEFAULT = '#test'
        resolve_video_substitution(['vEN3mQ0ql30', 'pIf2zL6aCig', 'YFwhijwNShw'], 'UFZPMKLKC')

    def test_run_video_scan(self):
        sub_videos_with_songs()

    def test_remove_all_vids_from_pl(self):
        pl_id = 'PL8xOIxSY5muCPboyeF4wGESVy7btDLqLG'
        guser_id = os.getenv('GOOGLE_USER_ID')
        usr = load_guser_by_id(guser_id)
        if usr.is_refresh_token_valid():
            if not usr.is_access_token_valid():
                # Replace with a token refresh
                refresh_access_token(usr)
        ytc = createYtMusic(usr.access_token, usr.refresh_token)
        playlist = ytc.get_playlist(pl_id, limit=None)
        tracks = playlist['tracks']
        videos = [t for t in tracks if t['videoType'] != 'MUSIC_VIDEO_TYPE_ATV']
        print(f"Removing {len(videos)} videos")
        print('\n'.join([f"{v['title']}" for v in videos]))
        if videos:
            ytc.remove_playlist_items(pl_id, videos)

    def test_list_jf_music_videos(self):
        metadata = {mm.yt_id: mm for mm in db.load_yt_media_metadata()}
        user = find_user_by_name(load_settings().jf_user_name)
        for pl_cfg in db.load_playlist_configs():
            playlist = jf.load_jf_playlist(pl_cfg.jf_pl_id, user.id, "Path,ProviderIds")
            itms = playlist['Items']
            no_yt_ids =[]
            no_meta =[]
            vids =[]
            songs =[]
            for it in itms:
                yt_id = get_nested_value(it, 'ProviderIds', 'YT')
                if not yt_id:
                    no_yt_ids.append(it)
                else:
                    meta = metadata.get(yt_id)
                    if meta:
                        if meta.category == Category.SONG:
                            songs.append(it)
                        else:
                            vids.append(it)
                    else:
                        no_meta.append(it)

            print(f"Playlist:       {pl_cfg.jf_pl_name}")
            print(f"Total:          {len(itms)}")
            print(f"No youtube id:  {len(no_yt_ids)}")
            print(f"No metadata:    {len(no_meta)}")
            print(f"Videos:         {len(vids)}")
            print(f"Songs:          {len(songs)}")

            print("\nNo meta:")
            for jfm in no_meta:
                print(jfm['Path'])
            print("\nVideos:")
            for jfm in vids:
                print(jfm['Path'])
            print('\n\n')

    def test_delete_jf_medias(self):
        vids = ['463f6d322843e69c6cc353b2a70bb43b', '5c9c6e8a60a0c285c2fc94953ba507a3', '54a9045576d677ce7883e58b1b935aef', '6e57015fd2ca246891aef452337ac887', 'a8afb490253275a8d059d2001fbd7b4d', 'be8936419fc05cbd5a603c1be10e2fb4', 'df9835a7babdfe7d966185c6cb4732ea', '7f62a9cc1663e0250adbc8d6f66025bd', '7417207d4a6bc58cc30dc55c7d468b18', 'fb5d0198241f610ac58ba3b07cd67d94', '542a629e16b07759387863aed3a692f6', '57a6009411b5ea319c820f61a52fc32b', '88f7676a171cd6a236b059b252d5105e', '1ad1b07a209f795c1afce07c635bdb96', '45308df4108316c0685427439b19ffc7', 'ffbabb15accbf6a7df3a7320c066152b', '1fbfbc2ae0f5c8ce372878bb1d8ff253', '445b9287d87dc7eea2d2fa6680fb8779', '361c80eee139cc6f5410984baf74d327', 'a01b7bb929e2b566c8b915693f38c6d4', '935423b971a4944d90121f6b6a6a2f89', '08f3bbbb505001b3d9c5dc9744fc6d38', '1b5e5e83c372867c9f7cbe77fe0a81d0', '20851a882e4684eb955fb7a1cd4d9a57', 'f7a7f623f71bcbf804693a65a37cc764', '3f7b671dbd993a6ed6b5aa8756e124cf', 'd9ee8c4418e00359eab7d84de0b01c3c', '119902934c63f186e94fd07484a9ba87', 'f6cb49a56b3d3f0c0cc7900999a81189', 'dbca56f3f373dff551c483ed9e3da224', '4af13f2fec271b3b8ae8b9e50418f153', 'c4a618a8ed33224060645f276fa1d75d', '25047cc4550cc7dde82fca53facfd4d4', '76a6e61a924870abfb91c391a3ab9b01', 'c06412434fc5f0d485311a2ce69804a7', 'e0c6ce0d3a14a626091ea7786553e3c4', '0bbc0da4a6c8af85c1ef94c6f1d6581d', '3c731f219aec0e0d9e6d87bd08d845a6', '782f65ddf297f1263f9eaed69192eb76', 'f4e3f3191ea5cf15f3f1e1c876991db4', 'c265cf9b7346e0e77bc892ee258a53b8', 'd3b4506398144ead2f1c78f80e60f19d', '6ff359614fbc39c73456bfd72ed3668e', '35db2bb06527a85ae1fa10ef5a7cfe21', '6733e638086da50e107d06ada5d31210', '426ebc81c609004996236f96de0dfaec', '38cd3f85acd7c2110fb1901adfaa8dcd', '1562059d70ae2a332e7bec088633fd84', '92ca3c3a52186635dfc513643b5ec2ba', '4938ac3e4e1b6831f9639070a1296f33', 'b713b03aa849e4b88fc7fe89e7159190', '00ef9287b553fc9708a2e1e21e1abb85', 'ff1b95bed0661ca0ae00c7fc3581b7e7', '6b8916f4cbd405c5e03b44ccb054209d', '2e71b35c9afcbc9bde1c9ada29f427aa', 'a76f98576f0345d670cbdcfffa97b253', '882b9aa6776db9cf3f4605da2dd216fe', 'a970805f1a7f34c101ce732a260a6c97', '597d68a01ab8f0f46885fc49a3b1b587', '550570402c29869bed33813e6464520f', '1911b515c8705dc417b8616b9b8bd941', '895f859080547f8a6d08f57e871ace33', 'e1fcbe07120dc2016141c7cd7ac887df', 'fac40861f5b6ffab6b2a7e2d1d50692b', '6c03f3be3decc4080adf9f3376be7d6d', '81b9de60f55397ba649ca297820531a6', '73ed4166ca8046c9805b0a57549b28df', 'd1d9e35b9df8f05e0b00954f937fcb91', '3879695a22fb7ff2cc3509011b9ac0f4', 'c0154a3445d88e5dd16f53c96a56eb7f', '757dfeed1acb213f2e23aa25fa9d546e', '3d7b3844b8d63ebef41fdb1d01af992f', 'fe55baaa956624eebde68107b1bf502c', '6d70285fab367a36ca23d4383ad57df6', '011bdd2bdddca0737123f3c4e87333ac', '49114fe986d9655d62c4456bf53b1286', '188aff67e66b0c92e7e8b7c01067aca8', 'a7ccb477b83ca13cb39a8d9ee152c726', 'bf940f9cc285f4189bd749af16808dfd', '331976c80c4bf421067ca419501dfe8c', 'dd888700f31ba0080da3642bfc2b2183', '39f63b88c91dd539e510c39749f92e56', '00a1927a9553b066261b1585e468c31e', '5c10102a75967daf226840ddde7f5905', '26bcab6fa371966d8537b8406f215a3f', 'ad650456094d8a3d0fa1d855a6ec7abd', 'acc02671496cdd72c9c5ecbaa23b43f8', '88a29a5a7210d1552c4535f9b7a457fd', '0bf7f17a5c088e6e49e35aad59ba79e3', '80d0bb196b636350cb9c874b404f8806', 'd6e5050b45205439cb0a823f50607643', 'f509c5d20fdec0d4dd22351854baeaa0', '915b010b40e8eeead4602c67083e2e29', '4f63972c69d07398c81fda76cf304a56', '14e267ac014830e0e7a72b51d8cfc534', '4661be4f73144dd254a380f2cc178315', '8bd7110ff33a932627de4602efebb613', '273bb4c399606eb5438b46e5251a91a3', '8b3a11c0df3697c22bde6ca4a5277250', '35739af9189a52f32466592463a79d7f', '2b22ab3258a3ac1b5ff99f1bc9217806', 'f12b3ca162010192e12f55069099c58a', 'c884ec213cbed7221a3ab82bd0529e04', 'd7bd21102cbbb92ddfd89e466d20c08d', '016d59faddf5d7411d4b422369322323', 'ece9cf0e6f4a4c30f5d3db93ab630553', '028a0566a91465bbcb474f3c9d613437', 'c98a4617d5120f534d85c2e458d9dfec', '658af27f59a6d4ae3f990b5c02e17bfb', 'bc5594b9f1a0ab29a5c3010bff84266b', 'adc29655fe6e3cab94ed048932c220ab', '616ede6de467b76339d6aca20435cfdc', '0eb817e47ec3614c99959b424a884452', 'ef80bd5c0e34436ad06fbd69fa660fbe', 'bbb9a04ac9fbabd9d4315a4e145dce20', '869207e68c7c0a2f47cf9291cf8d8fdc', '79299c2fcec85562738c8c1a8158f140', 'cf6f03dc1a24e16c35735ccc536b0287', 'dab0241a99e676fdc5f6a3255c923b1d', 'c7ce7f5869686ecec7231e3bff46fdee', 'eb8f68e5a193ce526db35b95ae6963bc', '826bf39b4cc34597e7cff56a0dae0e28', '604c2619fa84fee89a109a41e758a90e', 'bd3fc9db4005dcde5b9d566aa27eb3d6', 'a1dd9abc14e30371fec4f73dccb83419', 'b790886be2c4c4fab437adada9da0bd7', 'b6d7b420c4c0fe7ce974db80dc3abbf7', '553082ac8a0d6f71b4b6e0b50117d8e5', '0abc8468de64a2f20c640c3cfb4f21b4', 'c5a861a3b1718957d6f381324c34392c', 'da02a36435d7b77ba64c07d21b7b9621', '5047b865cff443fee10a6c2649621b57', 'fefe6fef95141f6cddef11f93430a57e', '1c66635d0a490c329aabf41a28745b64', '681a49cac00f30c78b26a9a92bb44a69', '855633af6c8fef76e26f039d18bcc6c7', 'c5315b4acf8003d3ea3a0d36ea920a81', '053fed3170b76e8ec701c897661de5e9', '5521e956f59383473e5d58ad76cb931a', '764fd9fa7a8835c4c9f898b695397781', 'a09038447c866697e0eb7b4fe50505e4', '1da19d53e2162b2b8db00069f7c31bb3', 'c29a676f66d750c2b6305c65443cfce8', '2ca7745fe3be46aea74a747dc8f3a80f', '4fb63577ccc6caceecc3934b2aae1681', '10c4262dc7b22937de5cb37a712ef4d2', 'd70a7e1bbd713e4397323b375f775a24', 'c5b1c18b8264b8d7050149aac1fadf79', 'd8e3747c4afc31c9d887c433a33fe117', '3d34b60bb7a2a852b4784588b6b73130', 'd8497a595721e20b53d16ea252adbb9c', '488308527afc383ecfbab9ace851b148', '615e229b6249b62f390bf8c8bca4306e', 'f6cb8a3e60508186f16d074c461911e8', '27167becd460bacf6445843bbfb4393f', 'f32d1bbb5661df90503c4b75d425701c', '224d2e35decba352be7f1d9c3ad19fe5', 'e1f7ff8028aa911d872f3151d3d90f23', '7ead036d0ba53ed6050b93adb0b88e1e', 'ac78cf4dc8c967da30c72c4f62d1eac9', '07c9948ac14c05baf423125887dd4294', 'bab181d416a654e9e56db007e65c8baf', '1cd132dfb921415ba9eb2897ced0ea7e', 'af5516b50c542f0300e2ba2f9a68f611', 'd89b4801310921a1d428e976b840a087', '566236b57d475fc9e53569cd578cb1be', '21cdcc24f75f3b5581be33f5aa5e19c1', '8eeb1bf2d04811fb42ede9d731ad051a', 'a8692c7717ed56f8c09627952267254e', 'f3651ecd12d4736b74fb6fe94aeea431', '89ac10f38bac193e44c6ceea37a89dc4', '608c35f6688d3330e83398deea4fd629', '809c3c7104af463406a8bbed95284d29', '74a8016abf9ab754f1320d851aecb0c3', '08e247ba97d11eee7330ab5115579978', '614ea4a2eaed5e006d159ee4fe767a46', '7eca4915ca2b0280b9db5ee1e6b77e99', '37af006888d91ded209b355ea66df18f', '03210ab4021e95fbae0bff2c1faf78cf', '76f1a247f8c6b66491894232fb24c681', 'ae6d2403884b0086e18ac31a34ee1c79', '8fc1af30fcbbc3332928b6cd36eddfbd', '3b468b006855ebeb1281bc0cc991f95c', '4446aa3e68a601125483bb89ad3198f7', '91adce7a5c37162e7b3bf5e6113af877', '25a39895025f55ce739178c1ec8a46b8', '980d678366acae7bdf5c62aff302f7e0', '73e9e597aee405a51851d3479bdade87', 'b7f78e88fbe447a2aed7126cf98f84c5', 'a39b05f0d9a584b8eed831ffd28e9517', '0f33e06a6cdf43b3995bfdbaa7b42052', '859ae61e8ded9fa019882d60cd496916', 'ef6d32ee9d69cbdb56e7ea556085a95a', '1a85188ff9a59b37359aadd91890c111', '16724a6522c6db264534d01df7d23c5f', '3695bedc9a98b45f67b628b6018cecbf', '2bcf09480ed7658e45039cae6d464f1c', '99aed6e25d3ef585724652ef0e408230', '7e308d6fc2886878c8137ee4c072e85f', '4aa764575e1d0756ba177bc119018c60', '0f020601b635953e974a258dcf22fcea', 'e05e7ca098f43bcd54b1c80358dc7442', '1493a13929119bc277f9a228f1bb41a7', '011daec56b1d8bbad4e4845d706ae8d1', 'fcb54bf31b67db45c10e7da79c51b989', '07f6b0c0f0587959741cdbde80aa8532', '5dee55c07c110947cd1032f2a848bf98', 'c72603df741ebdbc06cd0f92938d8c7e', 'ddeace6f5b43cc1100a6040c27d20fbf', '0e992228cb3b7e6166d8b680950a35b8', '2201d0e8a86dfdd4d7d9d6fe4aca96db', '1794456a8f40dc8372319d3d051c0988', 'f4dda498c440647fab04c2150c404360', '7957737365e87f96cbbd7f243b23ee7c', '62c534a6f54fa7887e743368d8d8374d', 'bb65a5e0cabeb2ef8db2a8d3ec33d71a', '88e82e023587b767dabac6336366c179', '4a4e18ab8c3019a961a86d2e6b247f6d', '26b2f0a5c97fdaf40c23c030d5166aef', 'bce8b6b6066a1d5d51eb6e4d2a31e4e5', '0f9d5ecc7972ebc0df52070a0a27f401', '8eaa455fd79b15689df9e1fb3881e2bd', '97a868364cf22da49eabca92d476d345', '3347541fd12e7bff33646b5f833e7d3b', '42bccaf9819e58b79d5ffebe36d2a2b3', '8932b84f18de3811b5a32d2583e22b95', 'b9260da296acbdb0b1696186dd3e8414', '24da45ac4654729ac6383685b0367daf', '8bd9a1d8de44ed3e2b6e4732b4502a8d']
        for vid in vids:
            resp = jf.__session__.delete(f"{jf.__jf_url__}/Items/{vid}")
            resp.raise_for_status()


    def test_docker(self):
        current_ctx = docker.context.Context.load_context(docker.context.api.get_current_context_name())
        url = current_ctx.endpoints["docker"]["Host"]
        client = docker.DockerClient(base_url=url)
        out = client.containers.run("bash", "echo 555", remove=True)
        print(out)


if __name__ == '__main__':
    unittest.main()
