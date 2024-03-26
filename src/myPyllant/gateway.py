#!/usr/bin/env python3

import argparse
import asyncio
import logging
import json
import sys
import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta

from myPyllant.api import MyPyllantAPI
# from api import MyPyllantAPI
from myPyllant.const import ALL_COUNTRIES, BRANDS, DEFAULT_BRAND
from myPyllant.enums import DHWOperationModeVRC700 as DHW_MODE
from myPyllant.enums import ZoneCurrentSpecialFunction as ZONE_FUNC

load_dotenv()

parser = argparse.ArgumentParser(
    description="Export data from myVaillant API   .")
parser.add_argument("-u", "--user", help="Username (email address) for the myVaillant app",
                    required=False, default=os.environ.get('VAILLANT_USER'))
parser.add_argument("-p", "--password", help="Password for the myVaillant app",
                    required=False, default=os.environ.get('VAILLANT_PASSWORD'))
parser.add_argument("-s", "--system", help="System ID",
                    required=False, default=os.environ.get('VAILLANT_SYSTEM_ID'))
parser.add_argument("-b", "--brand", help="Brand your account is registered in, i.e. 'vaillant'",
                    default=DEFAULT_BRAND, required=False, choices=BRANDS.keys())
parser.add_argument("cmd", help="Command to execute", default='status', choices=[
                    'status', 'dhw_mode', 'dhw_temperature', 'flow_temperature'])
parser.add_argument("-a", "--arg", help="Command argument",
                    required=False, type=str)
parser.add_argument("--country", help="Country your account is registered in, i.e. 'germany'",
                    default="poland", choices=ALL_COUNTRIES.keys(), required=False)
parser.add_argument("-v", "--verbose",
                    help="increase output verbosity", action="store_true")


async def call(user, password, brand, country, system_id, cmd: str, arg: str | float | None = None):
    async with MyPyllantAPI(user, password, brand, country) as api:
        try:
            system = await api.get_system(system_id)
        except Exception as e:
            print(json.dumps({"ack": False, "error": str(e)}))
            return

        if system:
            ack = False

            if cmd == 'status':
                status = {
                    "flow_temperature": system.circuits[0].current_circuit_flow_temperature,
                    "water_presure": system.water_pressure,
                    "outside_temperature": system.outdoor_temperature,
                    "tank_temperature": system.domestic_hot_water[0].current_dhw_temperature
                }

                print(json.dumps(status, indent=2))
                return
            elif cmd == 'dhw_mode' and arg is not None:
                arg = arg.lower() in ['true', '1', 'yes', 'on']
                mode = DHW_MODE.DAY if arg else DHW_MODE.OFF
                await api.set_domestic_hot_water_operation_mode(
                    system.domestic_hot_water[0], mode)

                ack = mode == system.domestic_hot_water[0].operation_mode_dhw
            elif cmd == 'dhw_temperature' and arg is not None:
                arg = int(arg)
                await api.set_domestic_hot_water_temperature(
                    system.domestic_hot_water[0], arg)

                ack = arg == system.domestic_hot_water[0].tapping_setpoint
            elif cmd == 'flow_temperature' and arg is not None:
                arg = float(arg)

                if arg > 5:
                    await api.quick_veto_zone_temperature(system.zones[0], arg, 5, 5)
                    ack = arg == system.zones[0].desired_room_temperature_setpoint and system.zones[
                        0].current_special_function == ZONE_FUNC.QUICK_VETO
                else:
                    await api.cancel_quick_veto_zone_temperature(system.zones[0])
                    ack = system.zones[0].current_special_function == ZONE_FUNC.NONE

            print(json.dumps({"ack": ack, "cmd": cmd, "arg": arg}))
        else:
            print(json.dumps({"ack": False, "error": "System not found!"}))


if __name__ == "__main__":
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)-5s - %(name)s - %(message)s')
        logging.getLogger('myPyllant.http_client').setLevel(logging.INFO)

    if not args.user or not args.password:
        raise ValueError('API user credentials not specified!')

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(call(args.user, args.password,
                DEFAULT_BRAND, args.country, args.system, args.cmd, args.arg))
