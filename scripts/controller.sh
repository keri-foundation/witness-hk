#!/bin/bash

kli init --name controller --salt 0ACDEyMzQ1Njc4OWxtbZctrl --nopasscode --config-dir ${WITOPNET_SCRIPT_DIR} --config-file controller
kli incept --name controller --alias controller --file ${WITOPNET_SCRIPT_DIR}/data/controller.json

WITNESS=$(curl -s -XPOST http://localhost:5631/witnesses -d'{"aid": "ENcOes8_t2C7tck4X4j61fSm0sWkLbZrEZffq7mSn8On"}' -H "Content-Type: application/json")

OOBI=$(echo "${WITNESS}" | jq -r .oobis[0])
EID=$(echo "${WITNESS}" | jq -r .eid)

echo "${WITNESS}"
kli oobi resolve --name controller --oobi-alias witness0 --oobi "${OOBI}"

kli witness authenticate --name controller --alias controller --witness "${EID}"

kli rotate --name controller --alias controller --witness-add "${EID}" --receipt-endpoint --authenticate
kli status --name controller --alias controller

kli rotate --name controller --alias controller --receipt-endpoint --authenticate
kli status --name controller --alias controller

WITNESS=$(curl -s -XPOST http://localhost:5631/witnesses -d'{"aid": "ENcOes8_t2C7tck4X4j61fSm0sWkLbZrEZffq7mSn8On"}' -H "Content-Type: application/json")

OOBI=$(echo "${WITNESS}" | jq -r .oobis[0])
EID=$(echo "${WITNESS}" | jq -r .eid)

kli oobi resolve --name controller --oobi-alias witness1 --oobi "${OOBI}"

kli witness authenticate --name controller --alias controller --witness "${EID}"

kli rotate --name controller --alias controller --witness-add "${EID}" --receipt-endpoint --authenticate

kli oobi generate --name controller --alias controller --role witness
