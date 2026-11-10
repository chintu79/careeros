import pytest
from unittest.mock import patch, MagicMock
from backend.app.connectors.greenhouse import GreenhouseConnector
from backend.app.connectors.lever import LeverConnector
from backend.app.connectors.ashby import AshbyConnector
from backend.app.connectors.remotive import RemotiveConnector
from backend.app.connectors.remoteok import RemoteOKConnector


@pytest.mark.asyncio
async def test_greenhouse_connector_mocked():
    """Verify Greenhouse connector parses jobs and normalizes them correctly."""
    mock_response = {
        "jobs": [
            {
                "id": 12345,
                "title": "Software Engineer Intern - Summer 2026",
                "content": "<p>Join our engineering team for a 3-month summer internship working with Python and React.</p>",
                "absolute_url": "https://boards.greenhouse.io/testco/jobs/12345",
                "location": {"name": "Remote, US"},
                "updated_at": "2026-05-01T12:00:00Z"
            },
            {
                "id": 99999,
                "title": "Senior Director of Infrastructure",
                "content": "<p>10+ years experience required.</p>",
                "absolute_url": "https://boards.greenhouse.io/testco/jobs/99999",
                "location": {"name": "New York, NY"}
            }
        ]
    }

    connector = GreenhouseConnector(board_id="testco", company_name="TestCo")
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        jobs = await connector.fetch_jobs(boards=[{"board_id": "testco", "company_name": "TestCo"}])
        # Only the internship should be accepted by strict filter
        assert len(jobs) == 1
        j = jobs[0]
        assert j["company_name"] == "TestCo"
        assert "Intern" in j["title"]
        assert j["source_platform"] == "greenhouse"
        assert j["external_id"] == "gh_12345"
        assert j["workplace_type"] == "remote"


@pytest.mark.asyncio
async def test_lever_connector_mocked():
    """Verify Lever connector parses postings and rejects non-internships."""
    mock_response = [
        {
            "id": "lever_abc_1",
            "text": "Machine Learning Research Intern",
            "categories": {"location": "San Francisco, CA", "workplaceType": "onsite"},
            "descriptionPlain": "Exciting internship opportunity for students and freshers.",
            "hostedUrl": "https://jobs.lever.co/testcomp/lever_abc_1",
            "createdAt": 1746000000000
        },
        {
            "id": "lever_abc_2",
            "text": "Principal Product Manager",
            "categories": {"location": "Remote"},
            "descriptionPlain": "Lead global product initiatives.",
            "hostedUrl": "https://jobs.lever.co/testcomp/lever_abc_2",
            "createdAt": 1746000000000
        }
    ]

    connector = LeverConnector(site="testcomp", company_name="TestComp")
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        jobs = await connector.fetch_jobs(sites=[{"site": "testcomp", "company_name": "TestComp"}])
        assert len(jobs) == 1
        j = jobs[0]
        assert j["company_name"] == "TestComp"
        assert "Intern" in j["title"]
        assert j["source_platform"] == "lever"
        assert j["external_id"] == "lever_lever_abc_1"


@pytest.mark.asyncio
async def test_ashby_connector_mocked():
    """Verify Ashby connector parses jobs correctly."""
    mock_response = {
        "jobs": [
            {
                "id": "ashby_job_1",
                "title": "Frontend Engineering Intern",
                "locationName": "Remote",
                "descriptionPlain": "Work on React, TypeScript, and modern frontend systems during a 6-month internship.",
                "jobUrl": "https://jobs.ashbyhq.com/testorg/ashby_job_1",
                "isRemote": True,
                "publishedAt": "2026-04-15T09:00:00Z"
            }
        ]
    }

    connector = AshbyConnector(organization="testorg", company_name="TestOrg")
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        jobs = await connector.fetch_jobs(orgs=[{"organization": "testorg", "company_name": "TestOrg"}])
        assert len(jobs) == 1
        j = jobs[0]
        assert j["company_name"] == "TestOrg"
        assert j["source_platform"] == "ashby"
        assert j["external_id"] == "ashby_ashby_job_1"
        assert j["workplace_type"] == "remote"


@pytest.mark.asyncio
async def test_remotive_connector_mocked():
    """Verify Remotive connector parses API response correctly."""
    mock_response = {
        "jobs": [
            {
                "id": 8888,
                "title": "Full Stack Developer Intern",
                "candidate_required_location": "Worldwide",
                "description": "<p>Remote internship working on web applications and APIs.</p>",
                "url": "https://remotive.com/remote-jobs/software-dev/full-stack-intern-8888",
                "company_name": "Remotive Partner",
                "publication_date": "2026-05-02T10:00:00Z",
                "salary": "$2,500 / month"
            }
        ]
    }

    connector = RemotiveConnector()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        jobs = await connector.fetch_jobs()
        assert len(jobs) == 1
        j = jobs[0]
        assert j["company_name"] == "Remotive Partner"
        assert j["source_platform"] == "remotive"
        assert j["stipend_text"] == "$2,500 / month"


@pytest.mark.asyncio
async def test_remoteok_connector_mocked():
    """Verify Remote OK connector parses remote listings and filters properly."""
    mock_response = [
        {"legal": "API usage notice"},
        {
            "id": "rok_101",
            "position": "Backend Python Intern",
            "company": "FastScale",
            "description": "Develop high-throughput REST APIs and data processing systems. Student internship.",
            "url": "https://remoteok.com/remote-jobs/rok_101",
            "location": "Worldwide",
            "epoch": 1746100000,
            "salary": "$30,000 - $40,000 / year"
        }
    ]

    connector = RemoteOKConnector()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        jobs = await connector.fetch_jobs()
        assert len(jobs) == 1
        j = jobs[0]
        assert j["company_name"] == "FastScale"
        assert j["source_platform"] == "remoteok"
        assert "rok_101" in j["external_id"]


@pytest.mark.asyncio
async def test_connectors_error_isolation():
    """Verify network errors or non-200 responses do not throw unhandled exceptions."""
    connector = GreenhouseConnector(board_id="invalid_board")
    with patch("httpx.AsyncClient.get", side_effect=Exception("Network timeout")):
        jobs = await connector.fetch_jobs()
        assert jobs == []
