"""Client HFSQL minimal, LECTURE SEULE, via iODBC en ANSI (ctypes).

Contourne pyodbc, incompatible avec le pilote PC SOFT sous iODBC
(SQLWCHAR 4 octets → débordement sur les appels « wide »). Ici tout passe
par les fonctions ANSI (SQLDriverConnect, SQLTables, SQLColumns, SQLGetData),
donc pas d'appel wide, pas de crash.

Volontairement limité à la lecture : connexion, métadonnées, et SELECT dont
les valeurs sont renvoyées en texte. Aucune écriture.
"""

from __future__ import annotations

import ctypes as C
from ctypes.util import find_library

# --- constantes ODBC ---
SQL_HANDLE_ENV, SQL_HANDLE_DBC, SQL_HANDLE_STMT = 1, 2, 3
SQL_SUCCESS, SQL_SUCCESS_WITH_INFO, SQL_NO_DATA, SQL_ERROR = 0, 1, 100, -1
SQL_ATTR_ODBC_VERSION, SQL_OV_ODBC3 = 200, 3
SQL_DRIVER_NOPROMPT = 0
SQL_C_CHAR = 1
SQL_NTS = -3
SQL_NULL_DATA = -1
SQL_NO_TOTAL = -4


def _decode(raw: bytes) -> str:
    """HFSQL peut renvoyer de l'UTF-8 ou du Windows-1252 selon les champs."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _load():
    name = find_library("iodbc") or "libiodbc.so.2"
    lib = C.CDLL(name)
    # toutes les fonctions SQL* renvoient un SQLRETURN (entier court signé)
    for fn in ("SQLAllocHandle", "SQLFreeHandle", "SQLSetEnvAttr",
               "SQLDriverConnect", "SQLDisconnect", "SQLExecDirect",
               "SQLFetch", "SQLGetData", "SQLNumResultCols", "SQLDescribeCol",
               "SQLTables", "SQLColumns", "SQLGetDiagRec", "SQLFreeStmt"):
        getattr(lib, fn).restype = C.c_short
    return lib


_lib = _load()


class HfsqlError(Exception):
    pass


def _diag(htype, handle):
    msgs = []
    i = 1
    while True:
        state = C.create_string_buffer(6)
        native = C.c_int(0)
        msg = C.create_string_buffer(2048)
        mlen = C.c_short(0)
        rc = _lib.SQLGetDiagRec(htype, handle, i, state, C.byref(native),
                                msg, 2048, C.byref(mlen))
        if rc not in (SQL_SUCCESS, SQL_SUCCESS_WITH_INFO):
            break
        msgs.append(f"[{_decode(state.value)}] "
                    f"{_decode(msg.value)}")
        i += 1
    return "\n".join(msgs) or "(pas de diagnostic)"


def _check(rc, htype, handle, what):
    if rc not in (SQL_SUCCESS, SQL_SUCCESS_WITH_INFO):
        raise HfsqlError(f"{what} : {_diag(htype, handle)}")


class Connection:
    def __init__(self, server, port, database, uid, pwd, driver_so,
                 extra="IntegrityCheck=1;"):
        self._env = C.c_void_p()
        self._dbc = C.c_void_p()
        _check(_lib.SQLAllocHandle(SQL_HANDLE_ENV, C.c_void_p(0), C.byref(self._env)),
               SQL_HANDLE_ENV, None, "AllocEnv")
        _lib.SQLSetEnvAttr(self._env, SQL_ATTR_ODBC_VERSION,
                           C.c_void_p(SQL_OV_ODBC3), 0)
        _check(_lib.SQLAllocHandle(SQL_HANDLE_DBC, self._env, C.byref(self._dbc)),
               SQL_HANDLE_ENV, self._env, "AllocDbc")
        # DRIVER sans accolades : iODBC ne les retire pas et échoue sinon.
        cs = (f"DRIVER={driver_so};Server Name={server};Server Port={port};"
              f"Database={database};UID={uid};PWD={pwd};{extra}").encode("latin-1")
        out = C.create_string_buffer(2048)
        outlen = C.c_short(0)
        rc = _lib.SQLDriverConnect(self._dbc, C.c_void_p(0), cs, len(cs),
                                   out, 2048, C.byref(outlen), SQL_DRIVER_NOPROMPT)
        _check(rc, SQL_HANDLE_DBC, self._dbc, "Connexion")

    # --- bas niveau ---
    def _stmt(self):
        h = C.c_void_p()
        _check(_lib.SQLAllocHandle(SQL_HANDLE_STMT, self._dbc, C.byref(h)),
               SQL_HANDLE_DBC, self._dbc, "AllocStmt")
        return h

    def _get(self, stmt, col):
        """Récupère une valeur en texte (gère les valeurs longues)."""
        chunks = []
        while True:
            buf = C.create_string_buffer(4096)
            ind = C.c_ssize_t(0)
            rc = _lib.SQLGetData(stmt, col, SQL_C_CHAR, buf, 4096, C.byref(ind))
            if rc == SQL_NO_DATA:
                break
            _check(rc, SQL_HANDLE_STMT, stmt, "GetData")
            if ind.value == SQL_NULL_DATA:
                return None
            # buf est terminé par NUL ; en cas de troncature on reboucle
            chunks.append(buf.value)
            if rc == SQL_SUCCESS:
                break
        return _decode(b"".join(chunks))

    # --- API lecture seule ---
    def query(self, sql):
        """Exécute un SELECT. Renvoie (colonnes, liste de lignes)."""
        stmt = self._stmt()
        try:
            # cp1252 + remplacement : évite un UnicodeEncodeError sur un terme
            # de recherche hors latin-1 (cohérent avec _decode).
            b = sql.encode("cp1252", "replace")
            _check(_lib.SQLExecDirect(stmt, b, len(b)),
                   SQL_HANDLE_STMT, stmt, "ExecDirect")
            return self._collect(stmt)
        finally:
            _lib.SQLFreeHandle(SQL_HANDLE_STMT, stmt)

    def _collect(self, stmt):
        ncol = C.c_short(0)
        _check(_lib.SQLNumResultCols(stmt, C.byref(ncol)),
               SQL_HANDLE_STMT, stmt, "NumResultCols")
        cols = []
        for i in range(1, ncol.value + 1):
            name = C.create_string_buffer(256); nlen = C.c_short(0)
            dt = C.c_short(0); sz = C.c_size_t(0); dd = C.c_short(0); nul = C.c_short(0)
            _lib.SQLDescribeCol(stmt, i, name, 256, C.byref(nlen),
                                C.byref(dt), C.byref(sz), C.byref(dd), C.byref(nul))
            cols.append(_decode(name.value))
        rows = []
        while True:
            rc = _lib.SQLFetch(stmt)
            if rc == SQL_NO_DATA:
                break
            _check(rc, SQL_HANDLE_STMT, stmt, "Fetch")
            rows.append([self._get(stmt, i) for i in range(1, ncol.value + 1)])
        return cols, rows

    def tables(self):
        stmt = self._stmt()
        try:
            _check(_lib.SQLTables(stmt, None, 0, None, 0, None, 0, b"TABLE", SQL_NTS),
                   SQL_HANDLE_STMT, stmt, "SQLTables")
            names = []
            while True:
                rc = _lib.SQLFetch(stmt)
                if rc == SQL_NO_DATA:
                    break
                _check(rc, SQL_HANDLE_STMT, stmt, "SQLTables")
                names.append(self._get(stmt, 3))  # TABLE_NAME = colonne 3
            return [n for n in names if n and not n.startswith("__")]
        finally:
            _lib.SQLFreeHandle(SQL_HANDLE_STMT, stmt)

    def columns(self, table):
        stmt = self._stmt()
        try:
            tb = table.encode("latin-1")
            _check(_lib.SQLColumns(stmt, None, 0, None, 0, tb, SQL_NTS, None, 0),
                   SQL_HANDLE_STMT, stmt, "SQLColumns")
            out = []
            while True:
                rc = _lib.SQLFetch(stmt)
                if rc == SQL_NO_DATA:
                    break
                _check(rc, SQL_HANDLE_STMT, stmt, "SQLColumns")
                out.append({"name": self._get(stmt, 4),       # COLUMN_NAME
                            "type": self._get(stmt, 6),       # TYPE_NAME
                            "size": self._get(stmt, 7)})      # COLUMN_SIZE
            return out
        finally:
            _lib.SQLFreeHandle(SQL_HANDLE_STMT, stmt)

    def count(self, table):
        cols, rows = self.query(f"SELECT COUNT(*) FROM [{table}]")
        return int(rows[0][0]) if rows else 0

    def close(self):
        try:
            _lib.SQLDisconnect(self._dbc)
        finally:
            _lib.SQLFreeHandle(SQL_HANDLE_DBC, self._dbc)
            _lib.SQLFreeHandle(SQL_HANDLE_ENV, self._env)
