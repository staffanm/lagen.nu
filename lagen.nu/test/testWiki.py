from ferenda.testutil import RepoTester, parametrize_repotester

# SUT
from wiki import MediaWiki, SFSMediaWiki

class TestWiki(RepoTester):
    repoclass = SFSMediaWiki
    docroot = "../../ferenda/test/files/repo/mediawiki"
parametrize_repotester(TestWiki)
