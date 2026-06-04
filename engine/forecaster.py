"""Forecaster module - handles disk usage prediction."""
from .utils import load_history, save_history


def forecast(dd, use_history=True):
    """Predict disk trends using history for linear regression."""
    warnings = []
    
    if use_history:
        hist = load_history()
        save_history(dd, hist)
    
    for n, d in dd.items():
        pct = d.get("p", 0)
        
        # Basic threshold warnings
        if pct > 95:
            warnings.append({
                "disk": n, "lvl": "critical",
                "msg": f"Disk {n} almost full ({pct}%)"
            })
        elif pct > 85:
            warnings.append({
                "disk": n, "lvl": "warning",
                "msg": f"Disk {n} running low ({pct}%)"
            })
        
        # History-based trend prediction
        if use_history and n in hist:
            pts = hist[n]
            if len(pts) >= 3:
                # Simple linear regression
                xs = list(range(len(pts)))
                ys = [p[1] for p in pts]
                n_pts = len(xs)
                sx = sum(xs)
                sy = sum(ys)
                sxy = sum(x * y for x, y in zip(xs, ys))
                sx2 = sum(x * x for x in xs)
                denom = n_pts * sx2 - sx * sx
                
                if denom != 0:
                    slope = (n_pts * sxy - sx * sy) / denom
                    
                    # Predict when disk will be full
                    if slope > 0.01:
                        days_to_full = int((100 - ys[-1]) / slope)
                        if days_to_full < 30:
                            warnings.append({
                                "disk": n, "lvl": "warning",
                                "msg": f"Disk {n} trending to full in ~{days_to_full} days (slope +{slope:.2f}%/day)"
                            })
    
    return warnings
