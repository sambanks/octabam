"""_fx1bad -- scratch."""
from remix.schema import Remix
REMIX = Remix(name="_fx1bad", doc="should be refused", modules=("REVERB SERVER", "SEND"),
              fallback="SEND", fx1=("REVERB SERVER",))
