#!/usr/bin/env python3
"""Exact five-hop reconstruction for H44F-B.

This searches the 32,768 canonical radio classes (UID2 low seven bits and
UID3). It does not search for, recover, or accept a binding phrase.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
from dataclasses import asdict, dataclass

CHANNEL_COUNT = 40
SYNC_CHANNEL = 20
FHSS_LENGTH = 240
OTA_VERSION = 4
REQUIRED_HOPS = 5
SEARCH_CLASSES = 1 << 15

_BASE_SEQUENCE = tuple(
    SYNC_CHANNEL if i % CHANNEL_COUNT == 0
    else 0 if i % CHANNEL_COUNT == SYNC_CHANNEL
    else i % CHANNEL_COUNT
    for i in range(FHSS_LENGTH)
)


def _xorshift32(state: int) -> int:
    if state == 0:
        state = 0x6D2B79F5
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


def _map_round(x: int, in_min: int, in_max: int,
               out_min: int, out_max: int) -> int:
    numerator = (x - in_min) * (out_max - out_min) * 2
    return (numerator // (in_max - in_min) + out_min * 2 + 1) // 2


def challenge_tuple(challenge: bytes, epoch: int,
                    throttle_channel: int) -> tuple[int, int, int, int]:
    state = 2166136261
    for byte in challenge:
        state = ((state ^ byte) * 16777619) & 0xFFFFFFFF
    for shift in range(0, 32, 8):
        state = ((state ^ ((epoch >> shift) & 0xFF)) * 16777619) & 0xFFFFFFFF
    state = state or 0xA5A55A5A
    values = []
    for _ in range(4):
        state = _xorshift32(state)
        crsf = _map_round(state & 0x3FF, 0, 1023, 172, 1811)
        values.append(_map_round(crsf, 172, 1811, 0, 1023))
    if 1 <= throttle_channel <= 4:
        values[throttle_channel - 1] = 0
    return tuple(values)  # type: ignore[return-value]


def decode_analog_tuple(raw_hex: str) -> tuple[int, int, int, int]:
    packet = bytes.fromhex(raw_hex)
    if len(packet) != 8:
        raise ValueError("OTA4 packet must contain eight bytes")
    packed = sum(packet[index + 1] << (8 * index) for index in range(5))
    return tuple((packed >> (10 * index)) & 0x3FF for index in range(4))  # type: ignore[return-value]


def packet_matches_challenge(raw_hex: str, challenge_hex: str,
                             throttle_channel: int) -> bool:
    challenge = bytes.fromhex(challenge_hex)
    if len(challenge) != 16:
        raise ValueError("challenge must contain sixteen bytes")
    actual = decode_analog_tuple(raw_hex)
    return any(actual == challenge_tuple(challenge, epoch, throttle_channel)
               for epoch in range(8))


@dataclass(frozen=True)
class Observation:
    fhss_index: int
    channel: int
    ota_nonce: int = 0
    slot_delta: int = 0
    raw: str = ""


@dataclass(frozen=True)
class Reconstruction:
    uid2_candidates: tuple[int, int]
    uid3: int
    uid4: int
    uid5: int
    crc_initializer: int
    canonical_seed: int
    alias_seed: int
    sequence: tuple[int, ...]
    sequence_sha256: str
    observations: tuple[Observation, ...]
    exact_matches: int
    adjacent_matches: int
    observation_model: str
    searched_classes: int = SEARCH_CLASSES


def seed_from(uid2: int, uid3: int, uid4: int, uid5: int) -> int:
    return (uid2 << 24) | (uid3 << 16) | (uid4 << 8) | (uid5 ^ OTA_VERSION)


def generate_fhss(seed: int) -> tuple[int, ...]:
    sequence = list(_BASE_SEQUENCE)
    state = seed & 0xFFFFFFFF
    for block in range(FHSS_LENGTH // CHANNEL_COUNT):
        offset = block * CHANNEL_COUNT
        for relative in range(1, CHANNEL_COUNT):
            index = offset + relative
            state = (214013 * state + 2531011) & 0x7FFFFFFF
            position = ((state >> 16) % (CHANNEL_COUNT - 1)) + 1
            other = offset + position
            sequence[index], sequence[other] = sequence[other], sequence[index]
    return tuple(sequence)


def validate_sequence(sequence: tuple[int, ...]) -> bool:
    return len(sequence) == FHSS_LENGTH and all(
        sequence[block * CHANNEL_COUNT] == SYNC_CHANNEL
        and sorted(sequence[block * CHANNEL_COUNT:(block + 1) * CHANNEL_COUNT])
        == list(range(CHANNEL_COUNT))
        for block in range(FHSS_LENGTH // CHANNEL_COUNT)
    )


def reconstruct(uid4: int, uid5: int,
                observations: list[Observation]) -> Reconstruction:
    if not 0 <= uid4 <= 0xFF or not 0 <= uid5 <= 0xFF:
        raise ValueError("UID4/UID5 outside one-byte range")
    unique: dict[int, Observation] = {}
    for observation in observations:
        if not 0 <= observation.fhss_index < FHSS_LENGTH:
            raise ValueError("FHSS index outside table")
        if not 0 <= observation.channel < CHANNEL_COUNT:
            raise ValueError("channel outside FCC915 table")
        previous = unique.get(observation.fhss_index)
        if previous is not None and previous.channel != observation.channel:
            raise ValueError("contradictory channel for one FHSS index")
        unique.setdefault(observation.fhss_index, observation)
    if len(unique) != REQUIRED_HOPS:
        raise ValueError(f"exactly {REQUIRED_HOPS} distinct positive hops required")

    selected = tuple(unique.values())
    exact_candidates: list[tuple[int, int, tuple[int, ...]]] = []
    adjacent_candidates: list[tuple[int, int, tuple[int, ...], int, int]] = []
    for uid2 in range(0x80):
        for uid3 in range(0x100):
            sequence = generate_fhss(seed_from(uid2, uid3, uid4, uid5))
            residuals = [abs(sequence[item.fhss_index] - item.channel)
                         for item in selected]
            exact = sum(value == 0 for value in residuals)
            adjacent = sum(value == 1 for value in residuals)
            if exact == REQUIRED_HOPS:
                exact_candidates.append((uid2, uid3, sequence))
            elif exact == REQUIRED_HOPS - 1 and adjacent == 1:
                adjacent_candidates.append((uid2, uid3, sequence, exact, adjacent))

    if len(exact_candidates) == 1:
        uid2a, uid3, sequence = exact_candidates[0]
        exact_matches, adjacent_matches = REQUIRED_HOPS, 0
        observation_model = "FIVE_EXACT"
    elif len(exact_candidates) > 1:
        raise ValueError("five exact hops do not identify one canonical radio class")
    elif len(adjacent_candidates) == 1:
        uid2a, uid3, sequence, exact_matches, adjacent_matches = adjacent_candidates[0]
        observation_model = "FOUR_EXACT_ONE_ADJACENT"
    elif len(adjacent_candidates) > 1:
        raise ValueError("one-adjacent model does not identify one canonical radio class")
    else:
        raise ValueError("no class matches five exact or four exact plus one adjacent")
    uid2b = uid2a | 0x80
    canonical_seed = seed_from(uid2a, uid3, uid4, uid5)
    alias_seed = seed_from(uid2b, uid3, uid4, uid5)
    if generate_fhss(alias_seed) != sequence or not validate_sequence(sequence):
        raise ValueError("UID2 high-bit alias invariant failed")
    crc_initializer = (((uid4 << 8) | uid5) ^ (OTA_VERSION << 8)) & 0xFFFF
    return Reconstruction(
        uid2_candidates=(uid2a, uid2b), uid3=uid3, uid4=uid4, uid5=uid5,
        crc_initializer=crc_initializer, canonical_seed=canonical_seed,
        alias_seed=alias_seed, sequence=sequence,
        sequence_sha256=hashlib.sha256(bytes(sequence)).hexdigest(),
        observations=selected,
        exact_matches=exact_matches,
        adjacent_matches=adjacent_matches,
        observation_model=observation_model,
    )


def write_artifacts(result: Reconstruction, json_path: pathlib.Path,
                    csv_path: pathlib.Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["uid2_candidates"] = [f"{value:02X}" for value in result.uid2_candidates]
    payload["uid3"] = f"{result.uid3:02X}"
    payload["uid4"] = f"{result.uid4:02X}"
    payload["uid5"] = f"{result.uid5:02X}"
    payload["crc_initializer"] = f"0x{result.crc_initializer:04X}"
    payload["canonical_seed"] = f"0x{result.canonical_seed:08X}"
    payload["alias_seed"] = f"0x{result.alias_seed:08X}"
    payload["sequence"] = list(result.sequence)
    payload["observations"] = [asdict(item) for item in result.observations]
    payload["binding_phrase_recovered"] = False
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["fhss_index", "channel", "frequency_hz", "sx1262_frequency_word"])
        for index, channel in enumerate(result.sequence):
            frequency = 903_500_000 + channel * 600_000
            writer.writerow([index, channel, frequency,
                             f"0x{((frequency << 25) // 32_000_000):08X}"])
