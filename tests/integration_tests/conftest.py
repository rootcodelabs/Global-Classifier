"""
Integration test harness for the dataset-generator module.

Brings up the minimal real slice of the BYK stack (Ruuter.public, Resql,
CronManager, SeaweedFS) via testcontainers' DockerCompose wrapper, plus the
tests/integration_tests/test_doubles stub standing in for Data Mapper,
notifications-node, and the real LLM-backed Dataset-Generator service. See
docker-compose-test.yml for what's real vs. stubbed and why.

Host ports are read directly from docker-compose-test.yml's fixed mappings
rather than via DockerCompose.get_service_port() - that call goes through
`docker compose port`, which proved flaky specifically for the cron-manager
service in this environment (intermittently reporting no published port for
a container that was demonstrably up and reachable). Since every port here
is already pinned in the compose file rather than dynamically assigned,
there's nothing to discover - connecting straight to the known localhost
port is simpler and more reliable than round-tripping through the CLI.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, Generator, Optional

import pytest
import requests
from loguru import logger
from testcontainers.compose import DockerCompose

HOST_PORTS = {
    "resql": 8082,
    "ruuter-public": 8086,
    "cron-manager": 9010,
    "seaweedfs": 9002,
    "test-doubles": 5050,
    "users_db": 5438,
}


class GCStackTestContainers:
    """Manages the minimal dataset-generator test stack."""

    def __init__(self, compose_file_name: str = "docker-compose-test.yml") -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.compose_file_path = self.project_root / compose_file_name
        self.compose: Optional[DockerCompose] = None
        self.ready_services: Dict[str, bool] = {}

        if not self.compose_file_path.exists():
            raise FileNotFoundError(
                f"Docker compose file not found: {self.compose_file_path}"
            )

    def start(self) -> None:
        logger.info("Starting dataset-generator test stack...")
        self.compose = DockerCompose(
            str(self.project_root),
            compose_file_name=self.compose_file_path.name,
            pull=False,
        )
        self.compose.start()
        self._wait_for_services()
        self._run_database_migration()
        logger.info("Dataset-generator test stack ready")

    def stop(self) -> None:
        if self.compose:
            logger.info("Stopping dataset-generator test stack...")
            self.compose.stop()

    def _wait_for_services(self) -> None:
        services = [
            ("resql", self._check_resql, 90),
            ("ruuter-public", self._check_ruuter_public, 90),
            ("cron-manager", self._check_cron_manager, 90),
            ("seaweedfs", self._check_seaweedfs, 60),
            ("test-doubles", self._check_test_doubles, 60),
        ]
        for name, check, timeout in services:
            self._wait_single(name, check, timeout)

    def _wait_single(self, name, check, timeout):
        logger.info(f"Waiting for {name}...")
        start = time.time()
        attempt = 0
        while time.time() - start < timeout:
            attempt += 1
            try:
                if check(HOST_PORTS[name]):
                    logger.info(f"{name} ready at localhost:{HOST_PORTS[name]}")
                    self.ready_services[name] = True
                    return
            except Exception as e:
                logger.debug(f"{name} - attempt {attempt} failed: {e}")
            time.sleep(3)
        raise TimeoutError(f"Timeout waiting for {name} after {timeout}s")

    def _check_resql(self, port: int) -> bool:
        try:
            r = requests.post(
                f"http://localhost:{port}/global-classifier/get-all-dataset-versions",
                json={},
                timeout=5,
            )
            return r.status_code < 500
        except Exception:
            return False

    def _check_ruuter_public(self, port: int) -> bool:
        # Ruuter has no route declared at "/", so it answers with a 500 once
        # it's up - any HTTP response at all (vs. a connection error) means ready.
        try:
            requests.get(f"http://localhost:{port}/", timeout=5)
            return True
        except Exception:
            return False

    def _check_cron_manager(self, port: int) -> bool:
        try:
            requests.get(f"http://localhost:{port}/", timeout=5)
            return True
        except Exception:
            return False

    def _check_seaweedfs(self, port: int) -> bool:
        # The S3 gateway answers /status once it is serving. Its root returns
        # 403 (credentials required), which is also a valid readiness signal
        # but less explicit.
        try:
            r = requests.get(f"http://localhost:{port}/status", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _check_test_doubles(self, port: int) -> bool:
        try:
            r = requests.get(f"http://localhost:{port}/_test/calls", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _run_database_migration(self) -> None:
        logger.info("Running Liquibase migration against the test database...")
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "gc-test-network",
                "-v",
                f"{self.project_root}/DSL/Liquibase/changelog:/liquibase/changelog",
                "-v",
                f"{self.project_root}/DSL/Liquibase/master.yml:/liquibase/master.yml",
                "-v",
                f"{self.project_root}/DSL/Liquibase/data:/liquibase/data",
                "liquibase/liquibase:4.33",
                "--defaultsFile=/liquibase/changelog/liquibase.properties",
                "--changelog-file=master.yml",
                "--url=jdbc:postgresql://users_db:5432/global-classifier?user=postgres",
                "--password=dbadmin",
                "update",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(self.project_root),
        )
        if result.returncode != 0:
            logger.error(f"Liquibase STDOUT: {result.stdout}")
            logger.error(f"Liquibase STDERR: {result.stderr}")
            raise RuntimeError("Database migration failed")
        logger.info("Database migration completed")

    def get_url(self, service: str) -> str:
        return f"http://localhost:{HOST_PORTS[service]}"


@pytest.fixture(scope="session")
def gc_stack() -> Generator[GCStackTestContainers, None, None]:
    stack = GCStackTestContainers()
    try:
        stack.start()
        yield stack
    finally:
        stack.stop()


@pytest.fixture(scope="session")
def ruuter_public_url(gc_stack: GCStackTestContainers) -> str:
    return gc_stack.get_url("ruuter-public") + "/global-classifier"


@pytest.fixture(scope="session")
def cron_manager_url(gc_stack: GCStackTestContainers) -> str:
    return gc_stack.get_url("cron-manager")


@pytest.fixture(scope="session")
def test_doubles_url(gc_stack: GCStackTestContainers) -> str:
    return gc_stack.get_url("test-doubles")


@pytest.fixture(scope="session")
def s3_client(gc_stack: GCStackTestContainers):
    """Host-reachable client, for uploading fixtures and managing buckets from
    the test process itself. minio-py is just an S3 client here - it talks to
    SeaweedFS's S3 gateway, not to MinIO."""
    from minio import Minio

    return Minio(
        f"localhost:{HOST_PORTS['seaweedfs']}",
        access_key="s3testkey",
        secret_key="s3testkey",
        secure=False,
    )


@pytest.fixture(scope="session")
def s3_internal_client(gc_stack: GCStackTestContainers):
    """Client addressed at the store's in-network hostname, for presigning URLs
    that the (containerized) pipeline script will fetch. That endpoint isn't
    reachable from the host, so `region` is pinned explicitly to skip minio-py's
    auto-detect call - presigning is pure local HMAC signing and needs no
    connectivity."""
    from minio import Minio

    return Minio(
        "seaweedfs:8333",
        access_key="s3testkey",
        secret_key="s3testkey",
        secure=False,
        region="us-east-1",
    )


@pytest.fixture(scope="session")
def postgres_client(gc_stack: GCStackTestContainers):
    import psycopg2

    # users_db isn't health-checked directly (migration waits for it); connect
    # via the host-mapped port declared in docker-compose-test.yml.
    host, port = "localhost", HOST_PORTS["users_db"]
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname="global-classifier",
                user="postgres",
                password="dbadmin",
            )
            yield conn
            conn.close()
            return
        except psycopg2.OperationalError:
            if attempt < max_attempts - 1:
                time.sleep(2)
            else:
                raise
