#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
from dataclasses import asdict, dataclass

CHANNEL_COUNT = 40
SYNC_CHANNEL = 20
FHSS_LENGTH = 240
OTA_VERSION = 4

_BASE_SEQUENCE = tuple(
    SYNC_CHANNEL if i % CHANNEL_COUNT == 0
    else 0 if i % CHANNEL_COUNT == SYNC_CHANNEL
    else i % CHANNEL_COUNT
    for i in range(FHSS_LENGTH)
)


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
    if len(sequence) != FHSS_LENGTH:
        return False

    counts = [0] * CHANNEL_COUNT
    for block in range(FHSS_LENGTH // CHANNEL_COUNT):
        chunk = sequence[
            block * CHANNEL_COUNT : (block + 1) * CHANNEL_COUNT
        ]
        if chunk[0] != SYNC_CHANNEL or sorted(chunk) != list(range(CHANNEL_COUNT)):
            return False
        for channel in chunk:
            counts[channel] += 1

    return counts == [FHSS_LENGTH // CHANNEL_COUNT] * CHANNEL_COUNT and all(
        sequence[i] != sequence[i - 1]
        for i in range(1, len(sequence))
    )


def sequence_sha256(sequence: tuple[int, ...]) -> str:
    return hashlib.sha256(bytes(sequence)).hexdigest()


def seed_from(uid2: int, uid3: int, uid4: int, uid5: int) -> int:
    return (
        (uid2 << 24)
        | (uid3 << 16)
        | (uid4 << 8)
        | (uid5 ^ OTA_VERSION)
    )


def _better(
    candidate: tuple[int, int, int],
    incumbent: tuple[int, int, int],
) -> bool:
    return (
        candidate[0] > incumbent[0]
        or (
            candidate[0] == incumbent[0]
            and (candidate[1], candidate[2]) < (incumbent[1], incumbent[2])
        )
    )


def reconstruct(
    uid4: int,
    uid5: int,
    observations: list[Observation],
) -> Reconstruction:
    if not observations:
        raise ValueError("no observations")

    unique: dict[tuple[int, int], Observation] = {}
    for observation in observations:
        if (
            0 <= observation.fhss_index < FHSS_LENGTH
            and 0 <= observation.channel < CHANNEL_COUNT
        ):
            unique.setdefault(
                (observation.fhss_index, observation.channel),
                observation,
            )

    observations = list(unique.values())
    if len(observations) < 3:
        raise ValueError(
            "at least three distinct positive observations are required"
        )

    midpoint = len(observations) // 2
    indexed = tuple(
        (observation.fhss_index, observation.channel)
        for observation in observations
    )

    best = (-1, 0, 0)
    second = (-1, 0, 0)
    first_best = (-1, 0, 0)
    second_best = (-1, 0, 0)

    # One single enumeration pass:
    # 128 canonical UID2 values × 256 UID3 values.
    for uid2 in range(0x80):
        fixed = (
            (uid2 << 24)
            | (uid4 << 8)
            | (uid5 ^ OTA_VERSION)
        )

        for uid3 in range(0x100):
            sequence = generate_fhss(fixed | (uid3 << 16))

            first_score = 0
            second_score = 0

            for position, (fhss_index, channel) in enumerate(indexed):
                if sequence[fhss_index] == channel:
                    if position < midpoint:
                        first_score += 1
                    else:
                        second_score += 1

            candidate = (first_score + second_score, uid2, uid3)

            if _better(candidate, best):
                second = best
                best = candidate
            elif _better(candidate, second):
                second = candidate

            first_candidate = (first_score, uid2, uid3)
            if _better(first_candidate, first_best):
                first_best = first_candidate

            second_candidate = (second_score, uid2, uid3)
            if _better(second_candidate, second_best):
                second_best = second_candidate

    best_score, uid2a, uid3a = best
    second_score = second[0]

    minimum_score = max(8, (len(observations) + 3) // 4)
    minimum_margin = max(4, (len(observations) + 9) // 10)

    split_ok = True
    split_detail = "not-required"

    if len(observations) >= 12:
        split_ok = (
            (first_best[1], first_best[2]) == (uid2a, uid3a)
            and (second_best[1], second_best[2]) == (uid2a, uid3a)
        )
        split_detail = (
            f"first={first_best[0]}:{first_best[1]:02X}:{first_best[2]:02X},"
            f"second={second_best[0]}:{second_best[1]:02X}:{second_best[2]:02X}"
        )

    if (
        best_score < minimum_score
        or best_score - second_score < minimum_margin
        or not split_ok
    ):
        raise ValueError(
            "no unique robust UID2/UID3 solution: "
            f"best={best_score}/{len(observations)} "
            f"uid2={uid2a:02X} uid3={uid3a:02X}, "
            f"second={second_score}, "
            f"margin={best_score - second_score}, "
            f"required_score={minimum_score}, "
            f"required_margin={minimum_margin}, "
            f"split={split_detail}"
        )

    uid2b = uid2a | 0x80
    canonical_seed = seed_from(uid2a, uid3a, uid4, uid5)
    alias_seed = seed_from(uid2b, uid3a, uid4, uid5)

    sequence_a = generate_fhss(canonical_seed)
    sequence_b = generate_fhss(alias_seed)

    if sequence_a != sequence_b or not validate_sequence(sequence_a):
        raise ValueError("candidate tables are not identical and valid")

    crc_initializer = (
        ((uid4 << 8) | uid5) ^ (OTA_VERSION << 8)
    ) & 0xFFFF

    return Reconstruction(
        uid2_candidates=(uid2a, uid2b),
        uid3=uid3a,
        uid4=uid4,
        uid5=uid5,
        crc_initializer=crc_initializer,
        canonical_seed=canonical_seed,
        alias_seed=alias_seed,
        sequence=sequence_a,
        sequence_sha256=sequence_sha256(sequence_a),
        observations=tuple(observations),
    )


def write_artifacts(
    result: Reconstruction,
    json_path: pathlib.Path,
    csv_path: pathlib.Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "uid2_candidates": [
            f"{value:02X}" for value in result.uid2_candidates
        ],
        "uid2_high_bit_ambiguous": True,
        "uid3": f"{result.uid3:02X}",
        "uid4": f"{result.uid4:02X}",
        "uid5": f"{result.uid5:02X}",
        "crc_initializer": f"0x{result.crc_initializer:04X}",
        "canonical_seed": f"0x{result.canonical_seed:08X}",
        "alias_seed": f"0x{result.alias_seed:08X}",
        "tables_identical": True,
        "sequence_sha256": result.sequence_sha256,
        "sequence": list(result.sequence),
        "observations": [
            asdict(observation)
            for observation in result.observations
        ],
    }

    json_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "fhss_index",
                "channel",
                "frequency_hz",
                "sx1262_frequency_word",
            ]
        )

        for index, channel in enumerate(result.sequence):
            frequency = 903_500_000 + channel * 600_000
            word = (frequency << 25) // 32_000_000
            writer.writerow(
                [index, channel, frequency, f"0x{word:08X}"]
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--uid4",
        required=True,
        type=lambda value: int(value, 0),
    )
    parser.add_argument(
        "--uid5",
        required=True,
        type=lambda value: int(value, 0),
    )
    parser.add_argument(
        "--observation",
        action="append",
        default=[],
        help="INDEX:CHANNEL",
    )
    parser.add_argument("--json")
    parser.add_argument("--csv")
    args = parser.parse_args()

    observations: list[Observation] = []
    for item in args.observation:
        index, channel = item.split(":", 1)
        observations.append(
            Observation(int(index, 0), int(channel, 0))
        )

    result = reconstruct(
        args.uid4,
        args.uid5,
        observations,
    )

    print(
        "H44F_CORE_RECONSTRUCTION_RESULT,"
        f"uid2_candidates="
        f"{result.uid2_candidates[0]:02X}|"
        f"{result.uid2_candidates[1]:02X},"
        f"uid3={result.uid3:02X},"
        f"uid4={result.uid4:02X},"
        f"uid5={result.uid5:02X},"
        f"crc_initializer=0x{result.crc_initializer:04X},"
        f"canonical_seed=0x{result.canonical_seed:08X},"
        f"alias_seed=0x{result.alias_seed:08X},"
        f"sequence_sha256={result.sequence_sha256},"
        "pass=1"
    )

    if args.json and args.csv:
        write_artifacts(
            result,
            pathlib.Path(args.json),
            pathlib.Path(args.csv),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
