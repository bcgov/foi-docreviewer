import maya

def pstformat(dt):
    if dt is not None:
        tolocaltime = maya.MayaDT.from_datetime(dt).datetime(
            to_timezone="America/Vancouver", naive=False
        )
        return tolocaltime.isoformat()
    else:
        return ""