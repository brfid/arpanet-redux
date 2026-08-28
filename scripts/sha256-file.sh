#!/bin/sh

set -eu

if [ "$#" -eq 0 ]; then
  echo "usage: $0 FILE [FILE ...]" >&2
  exit 64
fi

if command -v sha256sum >/dev/null 2>&1; then
  hash_backend=sha256sum
elif command -v shasum >/dev/null 2>&1; then
  hash_backend=shasum
elif command -v openssl >/dev/null 2>&1; then
  hash_backend=openssl
else
  echo "need sha256sum, shasum, or openssl" >&2
  exit 69
fi

for input_path do
  if [ ! -f "$input_path" ]; then
    echo "not a regular file: $input_path" >&2
    exit 66
  fi
  hash_directory=$(CDPATH= cd -- "$(dirname "$input_path")" && pwd)
  hash_path=$hash_directory/$(basename "$input_path")
  case $hash_backend in
    sha256sum)
      digest=$(sha256sum "$hash_path" | awk '{print $1}')
      ;;
    shasum)
      digest=$(shasum -a 256 "$hash_path" | awk '{print $1}')
      ;;
    openssl)
      digest=$(openssl dgst -sha256 "$hash_path" | awk '{print $NF}')
      ;;
  esac
  if [ "${#digest}" -ne 64 ]; then
    echo "invalid SHA-256 length for $input_path" >&2
    exit 1
  fi
  case $digest in
    *[!0-9A-Fa-f]*|'')
      echo "invalid SHA-256 output for $input_path" >&2
      exit 1
      ;;
  esac
  printf '%s  %s\n' "$digest" "$input_path"
done
