import asyncio
import datetime
import os
import subprocess
import unittest

import repour.asutil
import repour.asgit
from test import util

loop = asyncio.get_event_loop()
expect_ok = repour.asutil.expect_ok_closure()

class TestCommon(unittest.TestCase):
    def test_setup_commiter(self):
        with util.TemporaryGitDirectory() as repo:
            loop.run_until_complete(repour.asgit.setup_commiter(expect_ok, repo))
            out = subprocess.check_output(["git", "-C", repo, "config", "--local", "-l"])

        self.assertIn(b"user.name=", out)
        self.assertIn(b"user.email=", out)

    def test_fixed_date_commit(self):
        with util.TemporaryGitDirectory() as repo:
            with open(os.path.join(repo, "asd.txt"), "w") as f:
                f.write("Hello")
            util.quiet_check_call(["git", "-C", repo, "add", "-A"])
            loop.run_until_complete(repour.asgit.fixed_date_commit(expect_ok, repo, "Test"))
            out = subprocess.check_output(["git", "-C", repo, "log", "-1", "--pretty=fuller"])

        self.assertIn(b"AuthorDate: Thu Jan 1 00:00:00 1970 +0000", out)
        self.assertIn(b"CommitDate: Thu Jan 1 00:00:00 1970 +0000", out)

    def test_prepare_new_branch(self):
        with util.TemporaryGitDirectory() as repo:
            with open(os.path.join(repo, "asd.txt"), "w") as f:
                f.write("Hello")
            loop.run_until_complete(repour.asgit.prepare_new_branch(expect_ok, repo, "pull-1234567890", orphan=True))
            util.quiet_check_call(["git", "-C", repo, "commit", "-m", "Test"])

            with open(os.path.join(repo, "asd.txt"), "w") as f:
                f.write("Hello Hello")
            loop.run_until_complete(repour.asgit.prepare_new_branch(expect_ok, repo, "adjust-1234567890"))
            util.quiet_check_call(["git", "-C", repo, "commit", "-m", "Test"])

    def test_deduplicate_head_tag(self):
        with util.TemporaryGitDirectory() as remote:
            with open(os.path.join(remote, "asd.txt"), "w") as f:
                f.write("Hello")
            loop.run_until_complete(repour.asgit.prepare_new_branch(expect_ok, remote, "pull-1234567890", orphan=True))
            loop.run_until_complete(repour.asgit.fixed_date_commit(expect_ok, remote, "Pull"))
            loop.run_until_complete(repour.asgit.annotated_tag(expect_ok, remote, "pull-1234567890-root", "Some pull message"))

            with open(os.path.join(remote, "asd.txt"), "w") as f:
                f.write("Hello Hello")
            loop.run_until_complete(repour.asgit.prepare_new_branch(expect_ok, remote, "adjust-1234567890"))
            loop.run_until_complete(repour.asgit.fixed_date_commit(expect_ok, remote, "Adjust"))
            loop.run_until_complete(repour.asgit.annotated_tag(expect_ok, remote, "adjust-1234567890-root", "Some adjust message"))

            with util.TemporaryGitDirectory() as repo:
                with open(os.path.join(repo, "asd.txt"), "w") as f:
                    f.write("Hello")
                loop.run_until_complete(repour.asgit.prepare_new_branch(expect_ok, repo, "pull-568757645", orphan=True))
                loop.run_until_complete(repour.asgit.fixed_date_commit(expect_ok, repo, "Pull"))

                existing_tag = loop.run_until_complete(repour.asgit.deduplicate_head_tag(expect_ok, repo, remote))
                self.assertEqual(existing_tag, "pull-1234567890-root")

                with open(os.path.join(repo, "asd.txt"), "w") as f:
                    f.write("Hello Hello")
                loop.run_until_complete(repour.asgit.prepare_new_branch(expect_ok, repo, "adjust-256462457"))
                loop.run_until_complete(repour.asgit.fixed_date_commit(expect_ok, repo, "Adjust"))

                existing_tag = loop.run_until_complete(repour.asgit.deduplicate_head_tag(expect_ok, repo, remote))
                self.assertEqual(existing_tag, "adjust-1234567890-root")

                with open(os.path.join(repo, "asd.txt"), "w") as f:
                    f.write("Goodbye")
                loop.run_until_complete(repour.asgit.prepare_new_branch(expect_ok, repo, "adjust-257787787"))
                loop.run_until_complete(repour.asgit.fixed_date_commit(expect_ok, repo, "Adjust"))

                existing_tag = loop.run_until_complete(repour.asgit.deduplicate_head_tag(expect_ok, repo, remote))
                self.assertIsNone(existing_tag)

    def test_annotated_tag(self):
        with util.TemporaryGitDirectory() as repo:
            with open(os.path.join(repo, "asd.txt"), "w") as f:
                f.write("Hello")
            util.quiet_check_call(["git", "-C", repo, "add", "-A"])
            util.quiet_check_call(["git", "-C", repo, "commit", "-m", "Test"])
            loop.run_until_complete(repour.asgit.annotated_tag(expect_ok, repo, "pull-1234567890-root", "Annotation"))
            out = subprocess.check_output(["git", "-C", repo, "tag", "-l", "-n"])

        self.assertIn(b"pull-1234567890-root Annotation", out)

    def test_push_with_tags(self):
        with util.TemporaryGitDirectory(bare=True) as remote:
            with util.TemporaryGitDirectory(origin=remote) as repo:
                with open(os.path.join(repo, "asd.txt"), "w") as f:
                    f.write("Goodbye")
                util.quiet_check_call(["git", "-C", repo, "add", "-A"])
                util.quiet_check_call(["git", "-C", repo, "commit", "-m", "Test Commit"])
                util.quiet_check_call(["git", "-C", repo, "tag", "test-tag"])

                loop.run_until_complete(repour.asgit.push_with_tags(expect_ok, repo, "master"))

                remote_tags = subprocess.check_output(["git", "-C", repo, "tag", "-l", "-n"])

        self.assertIn(b"test-tag        Test Commit", remote_tags)


class TestPushNewDedupBranch(unittest.TestCase):
    def test_unix_time(self):
        ts = repour.asgit._unix_time()
        self.assertIsInstance(ts, int)
        ts_fixed = repour.asgit._unix_time(now=datetime.datetime(2015, 1, 1))
        self.assertIsInstance(ts_fixed, int)
        self.assertEqual(ts_fixed, 1420070400)

    def test_normal(self):
        with util.TemporaryGitDirectory(bare=True, ro_url="fake-ro-url") as remote:
            with util.TemporaryGitDirectory(origin=remote.readwrite) as repo:
                # Simulated pull
                with open(os.path.join(repo, "asd.txt"), "w") as f:
                    f.write("Hello")
                p = loop.run_until_complete(repour.asgit.push_new_dedup_branch(
                    expect_ok=expect_ok,
                    repo_dir=repo,
                    repo_url=remote,
                    operation_name="Pull",
                    operation_description="Blah",
                    orphan=True,
                    now=datetime.datetime(2015, 1, 1),
                ))
                self.assertEqual(
                    first=p,
                    second={
                        "branch": "pull-1420070400",
                        "tag": "pull-1420070400-root",
                        "url": {
                            "readwrite": remote.readwrite,
                            "readonly": "fake-ro-url",
                        },
                    },
                )

                # No changes
                nc = loop.run_until_complete(repour.asgit.push_new_dedup_branch(
                    expect_ok=expect_ok,
                    repo_dir=repo,
                    repo_url=remote,
                    operation_name="Adjust",
                    operation_description="Bleh",
                    no_change_ok=True,
                    now=datetime.datetime(2014, 1, 1),
                ))
                self.assertIsNone(nc)
                util.quiet_check_call(["git", "-C", repo, "checkout", "pull-1420070400"])

                # Changes
                with open(os.path.join(repo, "asd.txt"), "w") as f:
                    f.write("Hello Hello")
                c = loop.run_until_complete(repour.asgit.push_new_dedup_branch(
                    expect_ok=expect_ok,
                    repo_dir=repo,
                    repo_url=remote,
                    operation_name="Adjust",
                    operation_description="Bleh",
                    no_change_ok=True,
                ))
                self.assertIsNotNone(c)
                self.assertIn("branch", c)
                self.assertIn("adjust", c["branch"])
                self.assertIn("tag", c)
                self.assertIn("root", c["tag"])
                self.assertIn("url", c)
                self.assertEqual(remote.readwrite, c["url"]["readwrite"])
                self.assertEqual("fake-ro-url", c["url"]["readonly"])

                # Changes, already existing
                util.quiet_check_call(["git", "-C", repo, "checkout", "pull-1420070400"])
                with open(os.path.join(repo, "asd.txt"), "w") as f:
                    f.write("Hello Hello")
                ce = loop.run_until_complete(repour.asgit.push_new_dedup_branch(
                    expect_ok=expect_ok,
                    repo_dir=repo,
                    repo_url=remote,
                    operation_name="Adjust",
                    operation_description="Bleh",
                    now=datetime.datetime(2013, 1, 1),
                ))
                self.assertIsNotNone(ce)
                self.assertEqual(ce, c)
