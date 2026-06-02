"""
ChargeAlert TW — Rich Menu 圖片生成
產出 2500x1686 PNG,6 格(上下兩排各 3 格),供 LINE Rich Menu 用。
不依賴 emoji 字型:圖示用 Pillow 幾何繪製,中文用微軟正黑體。

用法(本機):  py make_rich_menu.py
輸出:        rich_menu.png(同目錄)
"""
from PIL import Image, ImageDraw, ImageFont

# ---- 規格 ----
W, H = 2500, 1686
COLS, ROWS = 3, 2
MARGIN = 40          # 外framework邊距
GAP = 30             # 格與格間距
RADIUS = 36          # 圓角

# ---- 配色(淺底版:讓整體畫面清爽,綠當點綴而非主色)----
BG = (244, 246, 250)        # 淺灰藍背景 #F4F6FA(跟儀表板一致)
TILE = (255, 255, 255)      # 白 tile
TILE_ALT = (241, 248, 241)  # 極淺綠(交錯,有層次但很淡)
BORDER = (210, 224, 210)    # 淺綠邊框(淺底要靠邊框分隔格子)
ICON = (22, 163, 74)        # 品牌綠 #16a34a(圖示色)
TEXT = (30, 58, 47)         # 深綠灰文字 #1E3A2F
ICON_BG_TINT = (241, 248, 241)  # 圖示後的圓形襯底(可選)

FONT_PATH = "C:/Windows/Fonts/msjh.ttc"

# ---- 6 格內容:(主標題, 圖示類型) ----
TILES = [
    ("我的縣市", "home"),
    ("選縣市",   "map"),
    ("各地天氣", "rain"),
    ("整體統計", "chart"),
    ("我的訂閱", "bell"),
    ("關於",     "info"),
]


def tile_rect(idx):
    """回傳第 idx 格(0-5)的 (x0,y0,x1,y1)。idx 順序:左到右、上到下。"""
    col = idx % COLS
    row = idx // COLS
    cell_w = (W - 2 * MARGIN - (COLS - 1) * GAP) / COLS
    cell_h = (H - 2 * MARGIN - (ROWS - 1) * GAP) / ROWS
    x0 = MARGIN + col * (cell_w + GAP)
    y0 = MARGIN + row * (cell_h + GAP)
    return (round(x0), round(y0), round(x0 + cell_w), round(y0 + cell_h))


def draw_icon(d, kind, cx, cy, s, color):
    """在 (cx,cy) 為中心畫一個尺寸約 s 的圖示。純幾何,不依賴字型。"""
    half = s / 2
    lw = max(8, s // 14)  # 線寬

    if kind == "home":
        # 屋頂三角 + 屋身方塊
        d.polygon([(cx, cy - half), (cx - half, cy), (cx + half, cy)], fill=color)
        d.rectangle([cx - half * 0.6, cy, cx + half * 0.6, cy + half * 0.7], fill=color)

    elif kind == "map":
        # 地圖定位 pin:圓 + 下尖
        r = half * 0.55
        d.ellipse([cx - r, cy - half * 0.7, cx + r, cy - half * 0.7 + 2 * r], fill=color)
        d.polygon([(cx - r * 0.7, cy - half * 0.7 + r * 1.3),
                   (cx + r * 0.7, cy - half * 0.7 + r * 1.3),
                   (cx, cy + half)], fill=color)
        d.ellipse([cx - r * 0.32, cy - half * 0.25, cx + r * 0.32, cy - half * 0.25 + r * 0.64], fill=(255, 255, 255))

    elif kind == "rain":
        # 雲 + 三條雨絲
        d.ellipse([cx - half * 0.8, cy - half * 0.5, cx + half * 0.2, cy + half * 0.2], fill=color)
        d.ellipse([cx - half * 0.2, cy - half * 0.7, cx + half * 0.8, cy + half * 0.1], fill=color)
        d.rectangle([cx - half * 0.7, cy - half * 0.1, cx + half * 0.7, cy + half * 0.2], fill=color)
        for dx in (-half * 0.45, 0, half * 0.45):
            d.line([(cx + dx, cy + half * 0.35), (cx + dx - s * 0.05, cy + half * 0.75)],
                   fill=color, width=lw)

    elif kind == "chart":
        # 三根長條
        bw = s * 0.18
        base = cy + half * 0.6
        heights = [half * 0.7, half * 1.1, half * 0.9]
        xs = [cx - bw * 1.8, cx - bw * 0.3, cx + bw * 1.2]
        for x, hh in zip(xs, heights):
            d.rectangle([x, base - hh, x + bw, base], fill=color)

    elif kind == "star":
        # 五角星
        import math
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            r = half if i % 2 == 0 else half * 0.42
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        d.polygon(pts, fill=color)

    elif kind == "bell":
        # 鈴鐺:上方小圓鈕 + 鐘body(梯形)+ 底部橫條 + 下方擺錘
        import math
        # 鐘身(用多邊形畫梯形鐘形)
        top_w = s * 0.30
        bot_w = s * 0.62
        d.polygon([
            (cx - top_w / 2, cy - half * 0.45),
            (cx + top_w / 2, cy - half * 0.45),
            (cx + bot_w / 2, cy + half * 0.30),
            (cx - bot_w / 2, cy + half * 0.30),
        ], fill=color)
        # 頂部小圓鈕
        br = s * 0.07
        d.ellipse([cx - br, cy - half * 0.62, cx + br, cy - half * 0.62 + 2 * br], fill=color)
        # 底部橫條
        d.rectangle([cx - bot_w * 0.62, cy + half * 0.30, cx + bot_w * 0.62, cy + half * 0.42], fill=color)
        # 下方擺錘
        cr = s * 0.09
        d.ellipse([cx - cr, cy + half * 0.45, cx + cr, cy + half * 0.45 + 2 * cr], fill=color)

    elif kind == "info":
        # 圓 + i
        d.ellipse([cx - half, cy - half, cx + half, cy + half], outline=color, width=lw)
        dot_r = s * 0.07
        d.ellipse([cx - dot_r, cy - half * 0.5 - dot_r, cx + dot_r, cy - half * 0.5 + dot_r], fill=color)
        d.rectangle([cx - dot_r, cy - half * 0.15, cx + dot_r, cy + half * 0.55], fill=color)


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 132)

    for idx, (label, icon) in enumerate(TILES):
        x0, y0, x1, y1 = tile_rect(idx)
        tile_color = TILE if (idx % 2 == 0) else TILE_ALT
        d.rounded_rectangle([x0, y0, x1, y1], radius=RADIUS, fill=tile_color,
                            outline=BORDER, width=3)

        cx = (x0 + x1) / 2
        # 圖示在上 1/3,文字在下 1/3
        icon_cy = y0 + (y1 - y0) * 0.36
        draw_icon(d, icon, cx, icon_cy, s=190, color=ICON)

        # 中文標題置中
        bbox = d.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        text_cy = y0 + (y1 - y0) * 0.72
        d.text((cx - tw / 2, text_cy - th / 2 - bbox[1]), label, font=font, fill=TEXT)

    img.save("rich_menu.png", "PNG", optimize=True)

    # 印出尺寸 + 檔案大小
    import os
    size_kb = os.path.getsize("rich_menu.png") / 1024
    print(f"已產出 rich_menu.png  {W}x{H}  {size_kb:.0f} KB")
    if size_kb > 1024:
        print("⚠️ 超過 1MB,LINE 上限是 1MB,需壓縮")
    else:
        print("✅ 檔案大小符合 LINE <1MB 規範")

    # 印出 6 格座標(階段 6 設 LINE action 區域用)
    print("\n=== Rich Menu 點按區域座標(階段 6 LINE Console 用)===")
    actions = ["action=home", "action=menu_charging", "action=menu_weather",
               "action=overall", "action=my_subs", "action=about"]
    for idx, (label, _) in enumerate(TILES):
        x0, y0, x1, y1 = tile_rect(idx)
        print(f"{label}: x={x0} y={y0} w={x1-x0} h={y1-y0}  → {actions[idx]}")


if __name__ == "__main__":
    main()