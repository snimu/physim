# Math font

`stix-two-math.woff2` is a subset of STIX Two Math (SIL Open Font License 1.1, see
`STIX-Two-Math-OFL.txt`), taken from the `@fontsource/stix-two-math` 5.3.0 npm package
(`files/stix-two-math-latin-400-normal.woff2`). The site stylesheet uses it for MathML so
radicals, large operators and accents render with an OpenType MATH table on every
system, including those without a math font installed.

The subset keeps the MATH table and the glyph variants it references:

```sh
pyftsubset stix-two-math-latin-400-normal.woff2 \
  --unicodes="U+0020-007E,U+00A0-00FF,U+02C6-02C7,U+0300-036F,U+0391-03C9,U+2000-206F,U+2100-214F,U+2190-21FF,U+2200-22FF,U+27E8-27EF,U+1D400-1D7FF" \
  --layout-features='*' --name-IDs='*' --name-languages='*' --notdef-outline \
  --flavor=woff2 --output-file=stix-two-math.woff2
```
