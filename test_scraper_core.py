#!/usr/bin/env python3
"""Secret-free regression tests for scraper filtering and retrieval policy."""

import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import scrape_jobs as sj

# A frozen fixture date becomes provably stale once real time passes it by
# MAX_POSTING_AGE_DAYS and the choke point starts rejecting every fixture
# row — so the default is always "yesterday".
FRESH_FIXTURE_DATE = (
    datetime.now(timezone.utc) - timedelta(days=1)
).strftime("%Y-%m-%dT%H:%M:%SZ")


def role(url="https://example.com/job/1", **overrides):
    job = {
        "company": "Acme", "title": "Account Manager",
        "location": "Los Angeles, CA", "url": url,
        "date_posted": FRESH_FIXTURE_DATE, "ats": "Test",
    }
    job.update(overrides)
    return job


class RoleAndLocationPolicy(unittest.TestCase):
    def test_biotech_company_matching_is_exact_not_substring_based(self):
        self.assertFalse(sj._is_biotech_company("Meta"))
        self.assertFalse(sj._is_biotech_company("Meta Platforms, Inc."))
        self.assertTrue(sj._is_biotech_company("Cytokinetics"))
        self.assertTrue(sj._is_biotech_company("Genentech, Inc."))
        self.assertTrue(sj._is_biotech_company("Buck Institute for Research on Aging"))

    def test_seniority_veto_is_word_bounded(self):
        for prefix in ("Senior", "Sr", "Sr.", "Staff", "Principal", "Director", "Founding"):
            self.assertFalse(sj.is_target_role(f"{prefix} Marketing Coordinator"), prefix)
        for title in (
            "Account Manager", "Community Manager", "Junior Project Manager",
            "Assistant Brand Manager", "Marketing Coordinator, Leadership Development",
            "Executive Assistant",
        ):
            self.assertTrue(sj.is_target_role(title), title)
        for title in (
            "Senior Account Manager", "General Manager, Client Services",
            "Regional Manager, Accounts", "VP Sales", "Head of Communications",
            "Director of Marketing",
        ):
            self.assertFalse(sj.is_target_role(title), title)

    def test_watch_location_accepts_la_oc_long_beach(self):
        accepted = (
            "Los Angeles, CA", "Long Beach, CA", "Burbank, CA", "Culver City, CA",
            "Santa Monica, CA", "Irvine, CA", "Anaheim, CA", "Orange, CA",
            "Greater Los Angeles Area", "Los Angeles Metropolitan Area",
        )
        for location in accepted:
            self.assertTrue(sj.is_watch_location(location), location)

    def test_watch_location_rejects_namesakes_and_out_of_region(self):
        rejected = (
            "Orange, NJ", "Glendale, AZ", "Long Beach, NY", "Norwalk, CT",
            "Pasadena, TX", "Hollywood, FL", "Westminster, CO",
            "San Francisco, CA", "New York, NY", "Riverside, CA", "San Diego, CA",
            "Remote", "Remote - USA",
        )
        for location in rejected:
            self.assertFalse(sj.is_watch_location(location), location)

    def test_remote_us_flag_flips_only_remote(self):
        with patch.object(sj, "INCLUDE_REMOTE_US", True):
            self.assertTrue(sj.is_watch_location("Remote - USA"))
            self.assertTrue(sj.is_watch_location("Remote"))
            self.assertFalse(sj.is_watch_location("New York, NY"))

    def test_filter_is_feed_aware_and_reports_stats(self):
        rows = [
            role("https://x/ok"),
            role("https://x/senior", title="Senior Account Manager"),
            role("https://x/far", location="Boston, MA"),
            role("https://x/company", company="Jack & Jill"),
            role("https://x/old", date_posted="2024-09-04"),
        ]
        kept, rejected, stats = sj._filter_job_observations(rows, default_feed="general")
        self.assertEqual([j["url"] for j in kept], ["https://x/ok"])
        self.assertEqual(kept[0]["feeds"], ["general"])
        self.assertEqual(stats, {"company": 1, "seniority": 1, "role": 0, "location": 1, "stale": 1})
        self.assertEqual({r["reason"] for r in rejected}, {"company", "seniority", "location", "stale"})
        bio, _, _ = sj._filter_job_observations(
            [role("https://x/bio", location="Burbank, CA")], default_feed="biotech")
        self.assertEqual(bio[0]["feeds"], ["biotech"])

    def test_stale_policy_at_the_choke_point(self):
        now = datetime.now(timezone.utc)

        def days_ago(n):
            return (now - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")

        rows = [
            role("https://x/fresh", date_posted=days_ago(13)),
            role("https://x/stale", date_posted=days_ago(15)),
            role("https://x/workday-old", date_posted="Posted 30+ Days Ago"),
            role("https://x/workday-fresh", date_posted="Posted 2 Days Ago"),
            role("https://x/undated", date_posted=""),
        ]
        kept, _, stats = sj._filter_job_observations(rows, default_feed="general")
        self.assertEqual(
            [j["url"] for j in kept],
            ["https://x/fresh", "https://x/workday-fresh", "https://x/undated"],
        )
        self.assertEqual(stats["stale"], 2)


class MasterPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir = sj.SCRIPT_DIR
        sj.SCRIPT_DIR = self.tmp.name

    def tearDown(self):
        sj.SCRIPT_DIR = self.old_dir
        self.tmp.cleanup()

    def read_master(self):
        with open(os.path.join(self.tmp.name, "all_jobs.json")) as f:
            return json.load(f)["jobs"]

    def test_canonical_identity_refreshes_and_preserves_first_seen(self):
        sj._merge_into_all_jobs([role("https://example.com/job/1?source=a", feeds=["general"])])
        first = self.read_master()[0]["first_seen"]
        sj._merge_into_all_jobs([role(
            "https://example.com/job/1?source=b", feeds=["biotech"],
            title="Marketing Coordinator", salary="$100k",
        )])
        jobs = self.read_master()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["first_seen"], first)
        self.assertEqual(jobs[0]["title"], "Marketing Coordinator")
        self.assertEqual(jobs[0]["feeds"], ["biotech", "general"])

    def test_rejection_removes_only_one_feed(self):
        sj._merge_into_all_jobs([role(feeds=["general", "biotech"])])
        sj._merge_into_all_jobs([], [{
            "identity": sj._job_identity("https://example.com/job/1"),
            "feed": "general", "reason": "location",
        }])
        self.assertEqual(self.read_master()[0]["feeds"], ["biotech"])
        sj._merge_into_all_jobs([], [{
            "identity": sj._job_identity("https://example.com/job/1"),
            "feed": "biotech", "reason": "seniority",
        }])
        self.assertEqual(self.read_master(), [])

    def test_accepted_duplicate_wins_over_same_feed_rejection(self):
        sj._merge_into_all_jobs([role(feeds=["general"])])
        first = self.read_master()[0]["first_seen"]
        sj._merge_into_all_jobs([role(feeds=["general"], salary="$120k")], [{
            "identity": sj._job_identity("https://example.com/job/1"),
            "feed": "general", "reason": "location",
        }])
        self.assertEqual(self.read_master()[0]["first_seen"], first)
        self.assertEqual(self.read_master()[0]["salary"], "$120k")


class RetrievalPolicy(unittest.TestCase):
    @staticmethod
    def card(job_id, title="Marketing Coordinator"):
        return (
            f'<li><div data-entity-urn="urn:li:jobPosting:{job_id}">'
            f'<h3 class="base-search-card__title">{title}</h3>'
            '<h4 class="base-search-card__subtitle">Acme</h4>'
            '<span class="job-search-card__location">Los Angeles, CA</span>'
            '<time datetime="2026-08-05"></time></div></li>'
        )

    def test_linkedin_advances_by_raw_page_size_and_stops_repeat(self):
        page = "".join(self.card(str(i)) for i in range(10))
        urls = []

        def fake_fetch(url):
            urls.append(url)
            return page

        with patch.object(sj, "LINKEDIN_LOCATIONS", [("Los Angeles, CA", "1")]), \
             patch.object(sj, "fetch", side_effect=fake_fetch), \
             patch.object(sj.time, "sleep"):
            jobs, raw = sj._linkedin_search(["marketing coordinator"], 3600)
        self.assertEqual(len(jobs), 10)
        self.assertEqual(raw, 20)  # repeated page is counted as received raw data
        self.assertEqual([re.search(r"start=(\d+)", u).group(1) for u in urls], ["0", "10"])

    def test_jobspy_retries_only_on_exactly_fifty(self):
        calls = []

        def fake(**kwargs):
            calls.append(kwargs["results_wanted"])
            return list(range(kwargs["results_wanted"]))

        self.assertEqual(len(sj._jobspy_fetch_with_retry(fake, site_name=["indeed"])), 100)
        self.assertEqual(calls, [50, 100])
        calls.clear()

        def short(**kwargs):
            calls.append(kwargs["results_wanted"])
            return list(range(49))

        self.assertEqual(len(sj._jobspy_fetch_with_retry(short)), 49)
        self.assertEqual(calls, [50])

    def test_jobspy_metro_radii(self):
        self.assertEqual(sj.JOBSPY_LOCATIONS, [("Los Angeles, CA", 30), ("Irvine, CA", 25)])


class RefilterCommand(unittest.TestCase):
    def test_biotech_repair_removes_meta_but_keeps_its_general_provenance(self):
        meta = role("https://x/meta", company="Meta", feeds=["biotech"])
        metagenomi = role(
            "https://x/metagenomi", company="Metagenomi", feeds=["biotech"])
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "discovered_companies.json"), "w") as f:
                json.dump([{"name": "Metagenomi"}], f)
            with open(os.path.join(tmp, "jobs.json"), "w") as f:
                json.dump({"jobs": [meta, metagenomi], "new_jobs": [meta, metagenomi]}, f)
            with open(os.path.join(tmp, "all_jobs.json"), "w") as f:
                master_meta = dict(meta, feeds=["general", "biotech"])
                json.dump({"jobs": [master_meta, metagenomi]}, f)
            with patch.object(sj, "SCRIPT_DIR", tmp):
                sj._BIOTECH_UNION_CACHE.clear()
                sj.repair_biotech_company_provenance(write=True)
            with open(os.path.join(tmp, "jobs.json")) as f:
                biotech = json.load(f)["jobs"]
            with open(os.path.join(tmp, "all_jobs.json")) as f:
                master = json.load(f)["jobs"]
        self.assertEqual([j["company"] for j in biotech], ["Metagenomi"])
        self.assertEqual([j["company"] for j in master], ["Meta", "Metagenomi"])
        self.assertEqual(master[0]["feeds"], ["general"])

    def test_preview_is_read_only_and_write_preserves_first_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "all_jobs.json")
            payload = {"updated_at": "old", "jobs": [
                role("https://x/keep", first_seen="2026-08-01T00:00:00Z"),
                role("https://x/drop", title="Senior Account Manager",
                     first_seen="2026-08-01T00:00:00Z"),
            ]}
            with open(path, "w") as f:
                json.dump(payload, f)
            with open(path) as f:
                before = f.read()
            with patch.object(sj, "SCRIPT_DIR", tmp):
                sj.refilter_existing_outputs(write=False)
                with open(path) as f:
                    self.assertEqual(f.read(), before)
                sj.refilter_existing_outputs(write=True)
            with open(path) as f:
                jobs = json.load(f)["jobs"]
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["first_seen"], "2026-08-01T00:00:00Z")

    def test_master_migration_uses_biotech_source_url_provenance(self):
        job = role("https://unknown-biotech.example/job/1", location="Culver City, CA")
        kept, stats = sj._refilter_master_jobs(
            [job], {sj._job_identity(job["url"])})
        self.assertEqual(stats["location"], 0)
        self.assertEqual(kept[0]["feeds"], ["biotech"])


class RegistrySaveIntegration(unittest.TestCase):
    def test_mixed_feeds_and_per_board_baseline_marker(self):
        rows = [
            role("https://registry/quiet", location="Irvine, CA", ats="Greenhouse",
                 feeds=["biotech"], registry_notify_eligible=False),
            role("https://registry/loud", location="Long Beach, CA", ats="Lever",
                 feeds=["general"], registry_notify_eligible=True),
        ]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(sj, "SCRIPT_DIR", tmp), \
             patch("notify.notify_new_jobs") as mocked_notify:
            sj.save_jobs_output(
                rows, basename="registry_jobs", title="Registry", subtitle="Test",
                accent="#000", empty_message="Empty", window_label="test",
                default_feed="general",
            )
            with open(os.path.join(tmp, "registry_jobs.json")) as f:
                saved = json.load(f)["jobs"]
        self.assertEqual([j["feeds"] for j in saved], [["biotech"], ["general"]])
        self.assertTrue(all("registry_notify_eligible" not in j for j in saved))
        notified = mocked_notify.call_args.args[0]
        self.assertEqual([j["url"] for j in notified], ["https://registry/loud"])


if __name__ == "__main__":
    unittest.main()
