from __future__ import annotations

import sys

if "--smoke-test" in sys.argv:
    from secret_manager.portable_smoke import main
else:
    from secret_manager.__main__ import main


if __name__ == "__main__":
    main()
