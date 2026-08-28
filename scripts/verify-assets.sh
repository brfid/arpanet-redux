#!/bin/sh

set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 PROFILE ARPANET_ROOT" >&2
  exit 64
fi

profile=$1
arpanet_root=$2
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
checksum_file="$repo_root/pins/arpanet-assets.sha256"

case $profile in
  router)
    path_pattern='src/linux-ncp/test/'
    required_directory="$arpanet_root/src/linux-ncp/test"
    ;;
  mixed)
    path_pattern='mini/'
    required_directory="$arpanet_root/mini"
    ;;
  all)
    path_pattern=''
    required_directory="$arpanet_root/mini"
    ;;
  *)
    echo "unknown asset profile: $profile" >&2
    exit 64
    ;;
esac

if [ ! -d "$required_directory" ]; then
  echo "asset profile root is missing: $required_directory" >&2
  exit 66
fi

verified_count=0
while read -r expected_digest relative_path; do
  case $expected_digest in
    ''|'#'*) continue ;;
  esac
  case $relative_path in
    "$path_pattern"*) ;;
    *) continue ;;
  esac
  actual_line=$("$repo_root/scripts/sha256-file.sh" "$arpanet_root/$relative_path")
  actual_digest=${actual_line%% *}
  if [ "$actual_digest" != "$expected_digest" ]; then
    echo "$relative_path: expected $expected_digest, found $actual_digest" >&2
    exit 1
  fi
  echo "$relative_path: OK"
  verified_count=$((verified_count + 1))
done <"$checksum_file"

if [ "$verified_count" -eq 0 ]; then
  echo "asset profile selected no files: $profile" >&2
  exit 1
fi
