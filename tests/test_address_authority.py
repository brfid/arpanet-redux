from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from ncc.address_authority import (
    AddressAuthorityError,
    address_authority,
    address_authority_from_mapping,
    host_address,
    host_address_octal,
    load_address_authority,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "config" / "authorities" / "nic-32992-1975-07.json"


def _document() -> dict:
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


class HostAddressArithmeticTests(unittest.TestCase):
    def test_derives_the_documented_rule(self) -> None:
        self.assertEqual(host_address(6, 1), 70)
        self.assertEqual(host_address(7, 1), 71)
        self.assertEqual(host_address(40, 0), 40)
        self.assertEqual(host_address(6, 3), 198)

    def test_octal_matches_the_repository_convention(self) -> None:
        self.assertEqual(host_address_octal(6, 1), "106")
        self.assertEqual(host_address_octal(7, 1), "107")
        self.assertEqual(host_address_octal(40, 0), "50")
        self.assertEqual(host_address_octal(6, 3), "306")

    def test_rejects_addresses_outside_the_short_leader_fields(self) -> None:
        for imp_number, host_number in ((0, 0), (64, 0), (6, 4), (6, -1)):
            with self.subTest(imp=imp_number, host=host_number):
                with self.assertRaises(AddressAuthorityError):
                    host_address(imp_number, host_number)

    def test_rejects_non_integers_including_booleans(self) -> None:
        for imp_number, host_number in ((True, 0), (6, True), ("6", 0), (6, 1.0)):
            with self.subTest(imp=imp_number, host=host_number):
                with self.assertRaises(AddressAuthorityError):
                    host_address(imp_number, host_number)


class ShippedAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.authority = address_authority("nic-32992-1975-07")

    def test_identifies_the_configured_its_host(self) -> None:
        identity = self.authority.identity(6, 1)
        self.assertIsNotNone(identity)
        self.assertEqual(identity.hostname, "MIT-DMS")
        self.assertEqual(identity.computer, "PDP-10")
        self.assertEqual(identity.operating_system, "ITS")
        self.assertEqual(identity.address_octal, "106")

    def test_identifies_the_only_host_whose_sole_operating_system_is_unix(self) -> None:
        identity = self.authority.identity(7, 1)
        self.assertIsNotNone(identity)
        self.assertEqual(identity.hostname, "RAND-ISO")
        self.assertEqual(identity.computer, "PDP-11/45")
        self.assertEqual(identity.operating_system, "UNIX")
        self.assertEqual(identity.address_octal, "107")
        sole_unix = [
            host
            for host in self.authority.hosts
            if host.operating_system == "UNIX"
        ]
        self.assertEqual([host.hostname for host in sole_unix], ["RAND-ISO"])

    def test_reports_the_vacant_slot_the_ncc_receiver_occupies(self) -> None:
        self.assertIsNone(self.authority.identity(5, 0))
        self.assertIsNotNone(self.authority.identity(5, 1))

    def test_rejects_imp_numbers_the_1975_network_had_not_reached(self) -> None:
        self.assertTrue(self.authority.within_network(58))
        self.assertFalse(self.authority.within_network(59))
        self.assertFalse(self.authority.within_network(62))

    def test_derived_addresses_never_disagree_with_the_source_rule(self) -> None:
        for host in self.authority.hosts:
            with self.subTest(hostname=host.hostname):
                self.assertEqual(
                    host.address_decimal,
                    host.imp_number + 64 * host.host_number,
                )

    def test_repeated_loads_share_one_immutable_instance(self) -> None:
        self.assertIs(address_authority("nic-32992-1975-07"), self.authority)

    def test_load_by_path_matches_load_by_name(self) -> None:
        self.assertEqual(load_address_authority(AUTHORITY_PATH), self.authority)


class AuthorityValidationTests(unittest.TestCase):
    def test_accepts_the_shipped_document(self) -> None:
        address_authority_from_mapping(_document())

    def test_rejects_an_unknown_field(self) -> None:
        document = _document()
        document["retired"] = True
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_a_missing_field(self) -> None:
        document = _document()
        del document["coverage_note"]
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_a_post_1975_addressing_rule(self) -> None:
        document = _document()
        document["address_rule"] = "decimal = imp_number + 256 * host_number"
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_a_row_beyond_the_declared_network(self) -> None:
        document = _document()
        document["hosts"].append(
            {"imp_number": 62, "host_number": 1, "hostname": "INVENTED", "status": "USER"}
        )
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_two_rows_at_one_host_position(self) -> None:
        document = _document()
        duplicate = copy.deepcopy(document["hosts"][0])
        duplicate["hostname"] = "SOMETHING-ELSE"
        document["hosts"].append(duplicate)
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_one_hostname_at_two_positions(self) -> None:
        document = _document()
        duplicate = copy.deepcopy(document["hosts"][0])
        duplicate["host_number"] = (duplicate["host_number"] + 1) % 4
        document["hosts"].append(duplicate)
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_an_unhashed_source(self) -> None:
        document = _document()
        document["source"]["sha256"] = "not-a-digest"
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_an_undated_source(self) -> None:
        document = _document()
        document["source"]["dated"] = "1975"
        with self.assertRaises(AddressAuthorityError):
            address_authority_from_mapping(document)

    def test_rejects_a_bare_name_that_escapes_the_authority_directory(self) -> None:
        for name in ("../secrets", ".hidden", "nested/name", ""):
            with self.subTest(name=name):
                with self.assertRaises(AddressAuthorityError):
                    address_authority(name)


if __name__ == "__main__":
    unittest.main()
