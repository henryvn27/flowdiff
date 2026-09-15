# FlowDiff site direction

Design read: this is a focused developer-tool page for the moment after two
dictation apps have been tested and someone needs a defensible next check. The
page should feel like a well-made project README with a point of view, not a
generic launch template.

## Audit of the previous version

- The warm paper, oversized headline, rounded navigation, rotated report card,
  and texture created a polished reference imitation before explaining how to
  use the tool.
- The hero featured a synthetic dashboard image with invented-looking scores,
  gradients, and status UI. It looked like a mockup rather than proof from the
  actual CLI.
- The only operational action was a run command. The install-from-repository
  step was missing, so the page did not describe a complete path to value.
- Large minimum heights and an art-directed image stack made the narrow layout
  feel sparse and repetitive.

## Decisions

- Variance 6: an asymmetric editorial layout with a real report excerpt as the
  visual anchor, but no rotation, texture, or decorative dashboard shell.
- Motion 2: one restrained entry transition and tactile link states. Reduced
  motion removes the transition layer.
- Density 5: install, run, use, method, and contract are all visible without
  filler sections.
- Palette: warm paper, ink, and one burnt-orange accent. No gradients.
- Type: local Avenir Next and a restrained Georgia contrast in the lead.
- Theme: one paper theme with a dark preference variant. Sections do not flip
  between unrelated surfaces.
- Proof: the page shows an excerpt derived from the included demo and a clear
  install command, run command, Codex prompt, and test command.

## Shared anti-slop rules

These are regression rules for future vibecoded project sites:

1. Write a product-specific design read before choosing a visual direction.
2. Lead with the real user path. For an installable repository, show install
   from the repo, run or use, expected result, and next action in that order.
3. Prefer real product output, source, or honest placeholders over fake product
   dashboards, invented metrics, fake testimonials, or decorative UI chrome.
4. Reject default AI patterns unless the product genuinely requires them:
   purple glow gradients, dark mesh heroes, three equal feature cards, pill
   navigation, rotated mockups, excessive rounded glass, status-dot clutter,
   version stamps, poetic filler labels, and repeated calls to action.
5. Re-read every visible string. No fake precision, broken phrases, em dashes,
   or claims that the implementation cannot prove.
6. Check desktop, narrow layout, keyboard focus, contrast, dark preference, and
   reduced motion before publishing.
7. Never ship an empty, placeholder, or low-quality icon slot. Use the wordmark
   alone unless a finished mark materially communicates the product and survives
   visual review in light, dark, and narrow layouts.

## Proof-of-concept flow

1. Clone the public repository and open `site/index.html` through a local
   static server.
2. Confirm the page shows the install command before the demo command.
3. Run the real demo and compare its result with the page excerpt.
4. Run the test suite.
5. Deploy the same `site/` folder with the GitHub Pages Actions workflow.
6. Verify the published URL, deployed commit, and workflow environment.
