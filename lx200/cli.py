from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

from .connection import SerialConnection, MockConnection, detect_serial_ports
from .protocol import LX200, parse_ra, parse_dec
from .catalog import resolve_name, best_entry, default_catalog_paths


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lx200", description="Controllo montatura Meade LX200 via seriale")
    p.add_argument("--port", help="Dispositivo seriale (es. /dev/cu.usbserial-XXXX)")
    p.add_argument("--baud", type=int, default=9600, help="Baud rate (default 9600)")
    p.add_argument("--timeout", type=float, default=2.0, help="Timeout lettura in secondi (default 2.0)")
    p.add_argument("--dry-run", action="store_true", help="Non invia comandi reali: stampa e simula risposte")

    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("detect", help="Elenca porte seriali disponibili")
    sp.add_parser("version", help="Mostra versione firmware montatura")
    sp.add_parser("status", help="Mostra RA/Dec correnti")

    find = sp.add_parser("find", help="Cerca oggetto per nome nei cataloghi locali")
    find.add_argument("--name", required=True, help="Nome/Designazione da cercare (es. Vega, HD 48915)")
    find.add_argument("--limit", type=int, default=5, help="Numero massimo di risultati")
    find.add_argument("--names-file", action="append", help="Percorso file CSV/JSON nomi (ripetibile)")

    goto = sp.add_parser("goto", help="Sposta a coordinate RA/Dec")
    goto.add_argument("--ra", help="RA target (HH:MM:SS o gradi/ore)")
    goto.add_argument("--dec", help="Dec target (+DD*MM:SS o gradi)")
    goto.add_argument("--ra-deg", type=float, help="RA in gradi (verrà convertita in ore)")
    goto.add_argument("--dec-deg", type=float, help="Dec in gradi decimali")

    goto_name = sp.add_parser("goto-name", help="Goto verso un oggetto per nome usando i cataloghi locali")
    goto_name.add_argument("--name", required=True, help="Nome/Designazione (es. Vega, HD 48915)")
    goto_name.add_argument("--names-file", action="append", help="Percorso file CSV/JSON nomi (ripetibile)")
    goto_name.add_argument("--index", type=int, default=0, help="Indice del risultato da usare (default: migliore)")

    move = sp.add_parser("move", help="Movimento manuale NSEW a rate specifico")
    move.add_argument("--dir", required=True, choices=["N", "S", "E", "W"], help="Direzione")
    move.add_argument("--rate", default="slew", choices=["guide", "center", "find", "slew"], help="Velocità")
    move.add_argument("--seconds", type=float, default=0.0, help="Durata in secondi (0 = continuo finché non si ferma)")

    stop = sp.add_parser("stop", help="Ferma i movimenti")
    stop.add_argument("--dir", choices=["N", "S", "E", "W"], help="Solo una direzione (se omesso ferma tutto)")

    sync = sp.add_parser("sync", help="Sincronizza la montatura a coordinate note")
    sync.add_argument("--ra", required=True, help="RA (HH:MM:SS o gradi/ore)")
    sync.add_argument("--dec", required=True, help="Dec (+DD*MM:SS o gradi)")

    return p


def resolve_port(args) -> Optional[str]:
    if args.port:
        return args.port
    # Prova auto-detect su macOS
    candidates = list(detect_serial_ports())
    return candidates[0] if candidates else None


def get_connection(args):
    if args.dry_run:
        return MockConnection()
    port = resolve_port(args)
    if not port:
        print("Nessuna porta seriale rilevata. Specifica --port.", file=sys.stderr)
        sys.exit(2)
    return SerialConnection(port=port, baudrate=args.baud, timeout=args.timeout)


def cmd_detect(args) -> int:
    ports = list(detect_serial_ports())
    if not ports:
        print("Nessuna porta trovata.")
        return 1
    for p in ports:
        print(p)
    return 0


def _names_paths(args):
    if args.names_file:
        return args.names_file
    return default_catalog_paths()


def cmd_version(args) -> int:
    conn = get_connection(args)
    with conn:
        lx = LX200(conn)
        v = lx.get_version()
        print(v)
    return 0


def cmd_status(args) -> int:
    conn = get_connection(args)
    with conn:
        lx = LX200(conn)
        ra = lx.get_ra()
        dec = lx.get_dec()
        print(f"RA:  {ra}")
        print(f"Dec: {dec}")
    return 0


def _pick_ra(args) -> str:
    if args.ra_deg is not None:
        return parse_ra(float(args.ra_deg))
    if args.ra is not None:
        return parse_ra(args.ra)
    raise SystemExit("Specificare --ra o --ra-deg")


def _pick_dec(args) -> str:
    if args.dec_deg is not None:
        return parse_dec(float(args.dec_deg))
    if args.dec is not None:
        return parse_dec(args.dec)
    raise SystemExit("Specificare --dec o --dec-deg")


def cmd_goto(args) -> int:
    conn = get_connection(args)
    with conn:
        lx = LX200(conn)
        ra = _pick_ra(args)
        dec = _pick_dec(args)
        lx.set_target_ra_dec(ra, dec)
        res = lx.goto()
        if res != "0" and not args.dry_run:
            print(f"Attenzione: risposta :MS non è '0': {res}", file=sys.stderr)
            return 2
        print(f"Goto avviato verso RA {ra}, Dec {dec}")
    return 0


def cmd_find(args) -> int:
    paths = _names_paths(args)
    results = resolve_name(args.name, limit=args.limit, paths=paths)
    if not results:
        print("Nessun risultato trovato. Specifica --names-file se necessario.")
        return 1
    for i, e in enumerate(results):
        mag = f" G={e.mag:.2f}" if e.mag is not None else ""
        print(f"[{i}] {e.name}{mag}  RA={e.ra_deg:.6f}°  Dec={e.dec_deg:.6f}°")
        if e.designations:
            print(f"    {e.designations}")
    return 0


def cmd_move(args) -> int:
    conn = get_connection(args)
    with conn:
        lx = LX200(conn)
        lx.set_rate(args.rate)
        lx.move_dir(args.dir)
        if args.seconds and args.seconds > 0:
            time.sleep(args.seconds)
            lx.stop_dir(args.dir)
    return 0


def cmd_stop(args) -> int:
    conn = get_connection(args)
    with conn:
        lx = LX200(conn)
        if args.dir:
            lx.stop_dir(args.dir)
        else:
            lx.stop_all()
    return 0


def cmd_sync(args) -> int:
    conn = get_connection(args)
    with conn:
        lx = LX200(conn)
        ra = parse_ra(args.ra)
        dec = parse_dec(args.dec)
        msg = lx.sync_to(ra, dec)
        print(msg)
    return 0


def cmd_goto_name(args) -> int:
    paths = _names_paths(args)
    results = resolve_name(args.name, limit=10, paths=paths)
    if not results:
        print("Nessun risultato trovato per il nome fornito.", file=sys.stderr)
        return 1
    target = None
    if args.index > 0 and args.index < len(results):
        target = results[args.index]
    else:
        target = best_entry(results)
    if not target:
        print("Impossibile selezionare un target valido.", file=sys.stderr)
        return 2
    # Converte gradi in formati LX200
    ra_hours = target.ra_deg / 15.0
    ra_str = parse_ra(ra_hours)
    dec_str = parse_dec(target.dec_deg)
    conn = get_connection(args)
    with conn:
        lx = LX200(conn)
        lx.set_target_ra_dec(ra_str, dec_str)
        res = lx.goto()
        if res != "0" and not args.dry_run:
            print(f"Attenzione: risposta :MS non è '0': {res}", file=sys.stderr)
            return 2
        print(f"Goto avviato verso {target.name} (RA {ra_str}, Dec {dec_str})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "detect":
        return cmd_detect(args)
    if args.cmd == "version":
        return cmd_version(args)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "find":
        return cmd_find(args)
    if args.cmd == "goto":
        return cmd_goto(args)
    if args.cmd == "goto-name":
        return cmd_goto_name(args)
    if args.cmd == "move":
        return cmd_move(args)
    if args.cmd == "stop":
        return cmd_stop(args)
    if args.cmd == "sync":
        return cmd_sync(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
