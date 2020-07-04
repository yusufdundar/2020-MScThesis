import asyncio
import json
import logging
import os
import random
import sys
import time

import numpy as np
import matplotlib.pyplot as plt

plt.style.use('seaborn-whitegrid')

from aiohttp import ClientError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa

from runners.support.agent import DemoAgent, default_genesis_txns
from runners.support.utils import (
    log_msg,
    log_status,
    log_timer,
    prompt,
    prompt_loop,
    require_indy,
)

CRED_PREVIEW_TYPE = (
    "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0/credential-preview"
)
SELF_ATTESTED = os.getenv("SELF_ATTESTED")

LOGGER = logging.getLogger(__name__)

TAILS_FILE_COUNT = int(os.getenv("TAILS_FILE_COUNT", 20))


class CourtAgent(DemoAgent):
    def __init__(
            self, http_port: int, admin_port: int, no_auto: bool = False, **kwargs
    ):
        super().__init__(
            "Court.Agent",
            http_port,
            admin_port,
            prefix="Court",
            extra_args=[]
            if no_auto
            else ["--auto-accept-invites", "--auto-accept-requests"],
            **kwargs,
        )
        self.connection_id = None
        self._connection_ready = asyncio.Future()
        self.cred_state = {}
        # TODO define a dict to hold credential attributes
        # based on credential_definition_id
        self.cred_attrs = {}

    async def detect_connection(self):
        await self._connection_ready

    @property
    def connection_ready(self):
        return self._connection_ready.done() and self._connection_ready.result()

    async def handle_connections(self, message):
        if message["connection_id"] == self.connection_id:
            if message["state"] in ["active", "response"]:
                self.log("Connected")
                self._connection_ready.set_result(True)
                if not self._connection_ready.done():
                    self._connection_ready.set_result(True)

    async def handle_issue_credential(self, message):
        state = message["state"]
        credential_exchange_id = message["credential_exchange_id"]
        prev_state = self.cred_state.get(credential_exchange_id)
        if prev_state == state:
            return  # ignore
        self.cred_state[credential_exchange_id] = state

        self.log(
            "Credential: state = {}, credential_exchange_id = {}".format(
                state, credential_exchange_id,
            )
        )

        if state == "request_received":
            log_status("#17 Issue credential to X")
            # issue credentials based on the credential_definition_id
            cred_attrs = self.cred_attrs[message["credential_definition_id"]]
            cred_preview = {
                "@type": CRED_PREVIEW_TYPE,
                "attributes": [
                    {"name": n, "value": v} for (n, v) in cred_attrs.items()
                ],
            }
            try:
                await self.issue_credential(cred_preview, credential_exchange_id)
            except ClientError:
                pass

    async def issue_credential(self, cred_preview, credential_exchange_id):

        await self.admin_POST(
            f"/issue-credential/records/{credential_exchange_id}/issue",
            {
                "comment": (
                    f"Issuing credential, exchange {credential_exchange_id}"
                ),
                "credential_preview": cred_preview,
            },
        )

    async def handle_present_proof(self, message):
        state = message["state"]

        presentation_exchange_id = message["presentation_exchange_id"]
        self.log(
            "Presentation: state =",
            state,
            ", presentation_exchange_id =",
            presentation_exchange_id,
        )

        if state == "presentation_received":
            log_status("#27 Process the proof provided by X")
            log_status("#28 Check if proof is valid")
            proof = await self.admin_POST(
                f"/present-proof/records/{presentation_exchange_id}/verify-presentation"
            )
            self.log("Proof =", proof["verified"])

    async def handle_basicmessages(self, message):
        self.log("Received message:", message["content"])


async def main(
        start_port: int,
        no_auto: bool = False,
        revocation: bool = False,
        show_timing: bool = False,
):
    genesis = await default_genesis_txns()
    if not genesis:
        print("Error retrieving ledger genesis transactions")
        sys.exit(1)

    agent = None

    try:
        log_status("#1 Provision an agent and wallet, get back configuration details")
        agent = CourtAgent(
            start_port,
            start_port + 1,
            genesis_data=genesis,
            no_auto=no_auto,
            timing=show_timing,
        )
        await agent.listen_webhooks(start_port + 2)
        await agent.register_did()

        with log_timer("Startup duration:"):
            await agent.start_process()
        log_msg("Admin URL is at:", agent.admin_url)
        log_msg("Endpoint URL is at:", agent.endpoint)

        # Create a schema
        with log_timer("Publish schema/cred def duration:"):
            log_status("#3/4 Create a new schema/cred def on the ledger")
            version = format(
                "%d.%d.%d"
                % (
                    random.randint(1, 101),
                    random.randint(1, 101),
                    random.randint(1, 101),
                )
            )
            (
                _,  # schema id
                credential_definition_id,
            ) = await agent.register_schema_and_creddef(
                "custody schema",
                version,
                [
                    "issuanceDate",
                    "issuer",
                    "trustFrameworkURI",
                    "auditURI",
                    "appealURI",
                    "caseResult",
                    "credentialSubject.holder.type",
                    "credentialSubject.holder.role",
                    "credentialSubject.holder.rationaleURI",
                    "credentialSubject.holder.firstName",
                    "credentialSubject.holder.lastName",
                    "credentialSubject.holder.kinshipStatus",
                    "credentialSubject.holder.constraints.boundaries",
                    "credentialSubject.holder.constraints.pointOfOrigin",
                    "credentialSubject.holder.constraints.radiusKM",
                    "credentialSubject.holder.constraints.jurisdictions",
                    "credentialSubject.holder.constraints.trigger",
                    "credentialSubject.holder.constraints.circumstances",
                    "credentialSubject.holder.constraints.startTime",
                    "credentialSubject.holder.constraints.endTime",
                    "credentialSubject.proxied.type",
                    "credentialSubject.proxied.firstName",
                    "credentialSubject.proxied.lastName",
                    "credentialSubject.proxied.birthDate",
                    "credentialSubject.proxied.photo",
                    "credentialSubject.proxied.iris",
                    "credentialSubject.proxied.fingerprint",
                    "credentialSubject.holder.permissions"
                ],
                support_revocation=revocation,
            )

        if revocation:
            with log_timer("Publish revocation registry duration:"):
                log_status(
                    "#5/6 Create and publish the revocation registry on the ledger"
                )
                await agent.create_and_publish_revocation_registry(
                    credential_definition_id, TAILS_FILE_COUNT
                )

        with log_timer("Generate invitation duration:"):
            # Generate an invitation
            log_status(
                "#7 Create a connection to alice and print out the invite details"
            )
            connection = await agent.admin_POST("/connections/create-invitation")

        agent.connection_id = connection["connection_id"]

        log_msg(
            json.dumps(connection["invitation"]), label="Invitation Data:", color=None
        )

        log_msg("Waiting for connection...")
        await agent.detect_connection()

        exchange_tracing = False
        options = (
            "    (1) Issue Credential\n"
            "    (2) Send Proof Request\n"
            "    (3) Send Message\n"
        )
        if revocation:
            options += (
                "    (4) Revoke Credential\n"
                "    (5) Publish Revocations\n"
                "    (6) Add Revocation Registry\n"
            )
        options += "    (T) Toggle tracing on credential/proof exchange\n"
        options += "    (X) Exit?\n[1/2/3/{}T/X] ".format(
            "4/5/6/" if revocation else ""
        )
        async for option in prompt_loop(options):
            if option is not None:
                option = option.strip()

            if option is None or option in "xX":
                break

            elif option in "tT":
                exchange_tracing = not exchange_tracing
                log_msg(
                    ">>> Credential/Proof Exchange Tracing is {}".format(
                        "ON" if exchange_tracing else "OFF"
                    )
                )

            elif option == "1":
                log_status("# Issue credential offer to X")

                offer_request = perform_time_measurement(agent, credential_definition_id, exchange_tracing)
                # offer_request = await prepare_cred(agent, credential_definition_id, exchange_tracing)
                await issue_cred(agent, offer_request)

            elif option == "2":
                log_status("#20 Request proof of degree from alice")
                req_attrs = [
                    {"name": "name", "restrictions": [{"issuer_did": agent.did}]},
                    {"name": "date", "restrictions": [{"issuer_did": agent.did}]},
                ]
                if revocation:
                    req_attrs.append(
                        {
                            "name": "degree",
                            "restrictions": [{"issuer_did": agent.did}],
                            "non_revoked": {"to": int(time.time() - 1)},
                        },
                    )
                else:
                    req_attrs.append(
                        {"name": "degree", "restrictions": [{"issuer_did": agent.did}]}
                    )
                if SELF_ATTESTED:
                    # test self-attested claims
                    req_attrs.append({"name": "self_attested_thing"}, )
                req_preds = [
                    # test zero-knowledge proofs
                    {
                        "name": "caseResult",
                        "p_type": "==",
                        "p_value": "joint-custody",
                        "restrictions": [{"issuer_did": agent.did}],
                    }
                ]
                indy_proof_request = {
                    "name": "Proof of Education",
                    "version": "1.0",
                    "requested_attributes": {
                        f"0_{req_attr['name']}_uuid": req_attr for req_attr in req_attrs
                    },
                    "requested_predicates": {
                        f"0_{req_pred['name']}_GE_uuid": req_pred
                        for req_pred in req_preds
                    },
                }
                if revocation:
                    indy_proof_request["non_revoked"] = {"to": int(time.time())}
                proof_request_web_request = {
                    "connection_id": agent.connection_id,
                    "proof_request": indy_proof_request,
                    "trace": exchange_tracing,
                }
                await agent.admin_POST(
                    "/present-proof/send-request", proof_request_web_request
                )
            elif option == "3":
                msg = await prompt("Enter message: ")
                await agent.admin_POST(
                    f"/connections/{agent.connection_id}/send-message", {"content": msg}
                )
            elif option == "4" and revocation:
                rev_reg_id = (await prompt("Enter revocation registry ID: ")).strip()
                cred_rev_id = (await prompt("Enter credential revocation ID: ")).strip()
                publish = json.dumps(
                    (await prompt("Publish now? [Y/N]: ", default="N")).strip()
                    in ("yY")
                )
                try:
                    await agent.admin_POST(
                        "/issue-credential/revoke"
                        f"?publish={publish}"
                        f"&rev_reg_id={rev_reg_id}"
                        f"&cred_rev_id={cred_rev_id}"
                    )
                except ClientError:
                    pass
            elif option == "5" and revocation:
                try:
                    resp = await agent.admin_POST(
                        "/issue-credential/publish-revocations", {}
                    )
                    agent.log(
                        "Published revocations for {} revocation registr{} {}".format(
                            len(resp["rrid2crid"]),
                            "y" if len(resp) == 1 else "ies",
                            json.dumps([k for k in resp["rrid2crid"]], indent=4),
                        )
                    )
                except ClientError:
                    pass
            elif option == "6" and revocation:
                log_status("#19 Add another revocation registry")
                await agent.create_and_publish_revocation_registry(
                    credential_definition_id, TAILS_FILE_COUNT
                )

        if show_timing:
            timing = await agent.fetch_timing()
            if timing:
                for line in agent.format_timing(timing):
                    log_msg(line)

    finally:
        terminated = True
        try:
            if agent:
                await agent.terminate()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False

    await asyncio.sleep(0.1)

    if not terminated:
        os._exit(1)


def prepare_cred(agent, credential_definition_id, exchange_tracing):
    agent.cred_attrs[credential_definition_id] = {
        "issuer": "https://moj.gov/issuers/14",
        "issuanceDate": str(int(time.time())),
        "trustFrameworkURI": "https://github.com/yusufdundar/2020-MScThesis/blob/master/custody-framework.md",
        "auditURI": "https://example.org/audit",
        "appealURI": "https://example.org/appeal",
        "caseResult": "joint-custody",
        "credentialSubject.holder.type": "Holder",
        "credentialSubject.holder.role": "kinship",
        "credentialSubject.holder.rationaleURI": "court-order",
        "credentialSubject.holder.firstName": "Alice",
        "credentialSubject.holder.lastName": "Smith",
        "credentialSubject.holder.kinshipStatus": "mother",
        "credentialSubject.holder.constraints.boundaries": "Within  Turkey  country  limits",
        "credentialSubject.holder.constraints.pointOfOrigin": "Ankara",
        "credentialSubject.holder.constraints.radiusKM": "1000",
        "credentialSubject.holder.constraints.jurisdictions": "tur",
        "credentialSubject.holder.constraints.trigger": "|en: Death of  parent",
        "credentialSubject.holder.constraints.circumstances": "|en: While a parent or adult sibling is unavailable, and no new guardian has been adjudicated",
        "credentialSubject.holder.constraints.startTime": "2007-07-01 T18:00",
        "credentialSubject.holder.constraints.endTime": "2025-08-01",
        "credentialSubject.proxied.type": "Proxied",
        "credentialSubject.proxied.firstName": "Charlie",
        "credentialSubject.proxied.lastName": "Smith",
        "credentialSubject.proxied.birthDate": "2007-07-01",
        "credentialSubject.proxied.photo": "https://raw.githubusercontent.com/yusufdundar/2020-MScThesis/master/charlie.base64",
        "credentialSubject.proxied.iris": "null",
        "credentialSubject.proxied.fingerprint": "null",
        "credentialSubject.holder.permissions": "routine-medical-care",
    }
    cred_preview = {
        "@type": CRED_PREVIEW_TYPE,
        "attributes": [
            {"name": n, "value": v}
            for (n, v) in agent.cred_attrs[credential_definition_id].items()
        ],
    }
    offer_request = {
        "connection_id": agent.connection_id,
        "cred_def_id": credential_definition_id,
        "comment": f"Offer on cred def id {credential_definition_id}",
        "auto_remove": False,
        "credential_preview": cred_preview,
        "trace": exchange_tracing,
    }
    return offer_request


def perform_time_measurement(agent, credential_definition_id, exchange_tracing):
    time1 = time.perf_counter()
    log_msg("-----1-----")
    log_status(time1)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time2 = time.perf_counter()
    log_msg("-----2-----")
    log_status(time2)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time3 = time.perf_counter()
    log_msg("-----3-----")
    log_status(time3)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time4 = time.perf_counter()
    log_msg("-----4-----")
    log_status(time4)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time5 = time.perf_counter()
    log_msg("-----5-----")
    log_status(time5)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time6 = time.perf_counter()
    log_msg("-----6-----")
    log_status(time6)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time7 = time.perf_counter()
    log_msg("-----7-----")
    log_status(time7)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time8 = time.perf_counter()
    log_msg("-----8-----")
    log_status(time8)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time9 = time.perf_counter()
    log_msg("-----9-----")
    log_status(time9)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time10 = time.perf_counter()
    log_msg("-----10-----")
    log_status(time10)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time11 = time.perf_counter()
    log_msg("-----11-----")
    log_status(time11)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time12 = time.perf_counter()
    log_msg("-----12-----")
    log_status(time12)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time13 = time.perf_counter()
    log_msg("-----13-----")
    log_status(time13)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time14 = time.perf_counter()
    log_msg("-----14-----")
    log_status(time14)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    time15 = time.perf_counter()
    log_msg("-----15-----")
    log_status(time15)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    prepare_cred(agent, credential_definition_id, exchange_tracing)
    offer_request = prepare_cred(agent, credential_definition_id, exchange_tracing)
    time16 = time.perf_counter()
    log_msg("-----16-----")
    log_status(time16)

    duration1 = time2 - time1
    duration2 = time3 - time2
    duration3 = time4 - time3
    duration4 = time5 - time4
    duration5 = time6 - time5
    duration6 = time7 - time6
    duration7 = time8 - time7
    duration8 = time9 - time8
    duration9 = time10 - time9
    duration10 = time11 - time10
    duration11 = time12 - time11
    duration12 = time13 - time12
    duration13 = time14 - time13
    duration14 = time15 - time14
    duration15 = time16 - time15

    durations = [duration1, duration2, duration3, duration4, duration5, duration6, duration7, duration8, duration9,
                 duration10, duration11, duration12, duration13, duration14, duration15]
    log_status(durations)
    log_status("durations yazdırdık")
    # convert to milliseconds:
    durations = [1000 * seconds for seconds in durations]

    log_status(durations)
    log_status("durations milisecond cinsinden yazdırdık")

    return offer_request


async def issue_cred(agent, offer_request):
    await agent.admin_POST("/issue-credential/send-offer", offer_request)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Runs a Court demo agent.")
    parser.add_argument("--no-auto", action="store_true", help="Disable auto issuance")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8020,
        metavar=("<port>"),
        help="Choose the starting port number to listen on",
    )
    parser.add_argument(
        "--revocation", action="store_true", help="Enable credential revocation"
    )
    parser.add_argument(
        "--timing", action="store_true", help="Enable timing information"
    )
    args = parser.parse_args()

    ENABLE_PYDEVD_PYCHARM = os.getenv("ENABLE_PYDEVD_PYCHARM", "").lower()
    ENABLE_PYDEVD_PYCHARM = ENABLE_PYDEVD_PYCHARM and ENABLE_PYDEVD_PYCHARM not in (
        "false",
        "0",
    )
    PYDEVD_PYCHARM_HOST = os.getenv("PYDEVD_PYCHARM_HOST", "localhost")
    PYDEVD_PYCHARM_CONTROLLER_PORT = int(
        os.getenv("PYDEVD_PYCHARM_CONTROLLER_PORT", 5001)
    )

    if ENABLE_PYDEVD_PYCHARM:
        try:
            import pydevd_pycharm

            print(
                "Court remote debugging to "
                f"{PYDEVD_PYCHARM_HOST}:{PYDEVD_PYCHARM_CONTROLLER_PORT}"
            )
            pydevd_pycharm.settrace(
                host=PYDEVD_PYCHARM_HOST,
                port=PYDEVD_PYCHARM_CONTROLLER_PORT,
                stdoutToServer=True,
                stderrToServer=True,
                suspend=False,
            )
        except ImportError:
            print("pydevd_pycharm library was not found")

    require_indy()

    try:
        asyncio.get_event_loop().run_until_complete(
            main(args.port, args.no_auto, args.revocation, args.timing)
        )
    except KeyboardInterrupt:
        os._exit(1)
