#!/usr/bin/env bash
set -e
npm run build:web && cd apps/mobile && npx cap sync android && cd android && ./gradlew assembleRelease
