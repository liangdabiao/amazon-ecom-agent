---
name: amazon-listing-creative
description: 'Amazon listing creative optimization — main image compliance, 7-slot secondary image strategy, bullet-point structure, and USP placement for CTR/CVR lift.\nUse when the user asks to design, review, or iterate on Amazon product images, bullet points, title, or A+ content; or when diagnosing low CTR / CVR on a listing.\nTriggers: 主图/副图/listing图片/图片设计/bullet points/标题优化/CTR低/CVR低/listing优化.\n'
description_zh: 优化 Amazon 主图合规、副图结构、五点与卖点位置，拉升点击率与转化率
benefits-from: []
user-invocable: true
risk-level: low
---

## When to use

Load this skill whenever the task touches:

- Designing or critiquing Amazon product images (main image, secondary images 2-7)
- Writing or rewriting bullet points / title
- Diagnosing why a listing has low CTR on search results or low CVR on the detail page
- Producing image briefs for a designer, Midjourney, 即梦, or other AI tools

## Hard compliance rules (do not violate)

These are Amazon policy. Violations can cause suppression or take-down.

### Main image (slot 1)

- **Pure white background — exactly `#FFFFFF`**, no gradients, no tint, no off-white
- **Product must fill ≥ 85%** of the frame
- **NO text, NO logos, NO watermarks, NO promotional badges** on the image itself
  - This includes "NEW", "BEST SELLER", "NO MONTHLY FEE", sale stickers, brand name overlays
  - Amazon's own "Amazon's Choice" / "Prime" badges are injected by Amazon, not by you
- **NO additional props, accessories, or models** that are not part of what the buyer receives
- **NO borders, mascots, or decorative elements**
- Real photograph preferred; pure AI-generated product renders risk "inaccurate representation" complaints
- Allowed exception: very small, neutral "NEW" badge is tolerated in some categories but risky — default to no text

**Common self-correction pitfall**: It is tempting to say "add a small 'NO MONTHLY FEE' angle badge to the main image to beat competitors." **This is wrong.** All USP/promotional text goes on secondary images (slots 2-7). Double-check before suggesting any text on slot 1.

### Secondary images (slots 2-7)

- Free to include: scene/lifestyle photos, infographics, comparison charts, text overlays, size charts, feature callouts, before/after shots, packaging layouts
- Still must be accurate — no fake night-vision samples, no staged features that the product does not actually have
- Recommended resolution: 2000×2000 square, RGB, JPG or PNG

### Product video (slot 8, optional)

- ≤ 30 seconds is the sweet spot
- Demonstrates actual product use, not just still images animated

## The 7-slot CVR strategy

Each image slot has a distinct job. Use this grid when briefing or critiquing:

| Slot | Job | What goes in it |
|------|-----|-----------------|
| 1 Main | Win the CTR on search results | Pure white bg, 45° hero angle, max clarity on the product's differentiator (e.g., visible solar panel on top) |
| 2 USP overview | Convince buyer to keep scrolling | Infographic with 4 core USPs as icon+headline+one-line benefit |
| 3 Comparison | Kill competitive doubt | Us vs "typical product" side-by-side; red ❌ on generic, green ✓ on ours; do NOT name competitor brands |
| 4 In-context / scene | Make it feel real | Product installed/used in the real environment (forest, kitchen, gym, etc.) |
| 5 App / tech / integration | Answer the "will it actually work?" fear | Phone UI mockup, connectivity diagram, signal coverage, etc. |
| 6 Effect sample | Show what the output looks like | Real sample output (photo/video/result). **Must be real**, not AI-faked, or reviews will tank |
| 7 What's in the box + warranty | Remove last purchase-friction | Overhead flat-lay of all accessories + warranty/support callouts |

## Bullet points: first-word rule

The first 3-6 characters of each bullet are what shoppers actually scan. Lead with the benefit in brackets, then the explanation:

```
✓ [NO MONTHLY FEE] Built-in SIM, pre-activated, no subscription. Save $120+/yr.
✓ [SOLAR + 7500mAh] Never change batteries. Runs for years unattended.
✓ [4K + 48MP] True 4K night vision with low-glow IR — crisp, undetected footage.
✓ [4G LTE APP] Real-time photos to phone, anywhere. No WiFi needed.
✓ [FULL KIT + 1-YR WARRANTY] Everything in box. US customer support.
```

Anti-pattern (what many Chinese sellers ship by default):
- Starting with "About Us" / "Technical Support" / "Why Choose" — these are self-centered and score zero scan value.
- Generic openings like "High Quality" / "Premium Materials" — shopper already assumed that.

## Small-category ads strategy interaction

If the product sits in a small category with a single dominant core keyword (e.g., `trail camera`, `neti pot`), the listing creative carries disproportionate weight because:

- You cannot afford to de-prioritize the core keyword to chase long-tail efficiency — there is no long-tail pool big enough
- Bid reduction on the core keyword = losing the position you paid to earn
- **The only levers are CTR (main image + price + rating visual weight) and CVR (secondary images + bullets + reviews)**

When diagnosing "core keyword is burning budget," the fix order is:

1. Main image redesign — biggest CTR lever
2. Placement bid modifiers — push Top-of-Search +30–100%, cut Product Pages to 0 or negative
3. Bidding strategy → "Down only" (stops A9 from topping up bids in low-converting placements)
4. Bullet + A+ rewrite → CVR lift
5. Review velocity (Vine, post-purchase follow-up) → CVR ceiling
6. **Only after 1-5 are exhausted** consider splitting the core keyword into a Top-of-Search-only dedicated campaign

## Image brief template (for designer / AI tool)

When producing briefs, use this structure per slot:

```
Slot: <number + name>
Background: <white / wood / scene>
Subject: <product angle, size, position>
Text overlays: <exact copy, short>
Callouts: <icons + short labels>
Forbidden: <list things that must NOT appear>
Style reference: <optional — competitor listings that hit this note well>
```

Keep copy short. English bullets on secondary images should be ≤ 7 words per line; users read while scrolling fast.

## AI-tool usage (Midjourney / 即梦 / DALL-E / Canva)

- **Product shots**: Midjourney and 即梦 can produce credible hero/scene images but will drift from the real product. Always cross-check that the rendered unit matches the real SKU's button layout, logo, port placement.
- **Infographics & comparison charts (slots 2, 3, 5, 7)**: Canva or 创客贴 with Amazon listing templates is faster and cleaner than Midjourney.
- **Sample output images (slot 6)**: Must be real photos from the actual product, not AI. Fake sample output is the top cause of "doesn't match description" reviews.

## Pitfalls

- **Putting text on the main image** — policy violation, can cause suppression. Never suggest this.
- **Using competitor brand names** on comparison images — trademark risk. Use "Typical Cellular Camera" / "Most Brands" instead.
- **AI-generated night-vision or thermal samples** — invites "false advertising" reviews. Use real samples only.
- **Five bullets all starting the same way** (all "High quality…") — wastes the scanning position. Vary lead words.
- **Main image with the product straight-on flat** — loses the visual hook. 45° angle almost always wins when the product has a signature feature on top or side (solar panel, screen, etc.).
- **Forgetting the differentiator in slot 1** — if your USP is "solar powered" but the main image hides the solar panel behind a straight-on shot, buyers never know in the 0.3 sec scan.

## Output style when responding

- Produce **design briefs**, not paragraph descriptions, when the user asks for images
- Give buyer-facing English copy in clean code blocks so the user can paste directly to designer / AI tool
- Label every slot (Slot 1 / Slot 2 …) so the user knows the order
- Always remind the user: slot 6 (sample output) should be real, not AI
