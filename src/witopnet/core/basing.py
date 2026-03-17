# -*- encoding: utf-8 -*-
from dataclasses import dataclass

from keri import core
from keri.db import dbing, koming, subing


@dataclass
class Wit:
    """Persisted record for a single provisioned witness.

    Attributes:
        name (str): internal keystore name for the witness Hab
        eid (str): qb64 AID of the witness identifier
        cid (str): qb64 AID of the controller this witness serves
    """

    name: str
    eid: str
    cid: str


class Baser(dbing.LMDBer):
    """LMDB database for the Witness Operational Network.

    Extends the base KERI LMDBer with three sub-databases:
        - ``wits``: witness records keyed by witness AID
        - ``cids``: controller-AID-to-witness-AID index
        - ``codes``: encrypted TOTP codes keyed by (controller AID, witness AID)
    """

    TailDirPath = "keri/witopnet"
    AltTailDirPath = ".keri/witopnet"
    TempPrefix = "keri_witopnet_"

    def __init__(self, name="witopnet", headDirPath=None, reopen=True, **kwa):
        """
        Parameters:
            name (str): database name, also used as the directory name
            headDirPath (str | None): optional override for the database head directory
            reopen (bool): if True, open the database immediately on construction
            **kwa: additional keyword arguments forwarded to LMDBer
        """
        self.wits = None
        self.cids = None
        self.codes = None

        super(Baser, self).__init__(
            name=name, headDirPath=headDirPath, reopen=reopen, **kwa
        )

    def reopen(self, **kwa):
        """Reopen database and initialize sub-dbs"""
        super(Baser, self).reopen(**kwa)
        # Witness dataclass keyed by witness AID
        self.wits = koming.Komer(
            db=self,
            subkey="wits.",
            schema=Wit,
        )
        # Controller AID to witness AID index
        self.cids = subing.IoSetSuber(db=self, subkey="cids.")
        # Witness to project index key is Witness prefix val is Project SAID
        self.codes = subing.CesrSuber(db=self, subkey="codes.", klas=core.Cipher)

        return self.env
