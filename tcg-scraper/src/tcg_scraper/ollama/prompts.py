IDENTIFY_PROMPT = """You are looking at a photo of a single physical trading card (Pokemon, Magic: The Gathering, One Piece, Yu-Gi-Oh, or a similar TCG).

Identify the card and respond with ONLY a JSON object (no other text) with exactly these keys:

{
  "name": "the card's name/title as printed, or null if unreadable",
  "number": "the collector/card number as printed (e.g. '025/165' or '070'), or null if unreadable",
  "set": "the set/expansion name if you can identify or read it, or null if unknown",
  "language": "the print language if determinable from the text (e.g. 'English', 'Japanese'), or null",
  "variant": "any visible finish/variant note (e.g. 'Holo', 'Reverse Holo', '1st Edition'), or null",
  "game": "which TCG this card is from if identifiable (e.g. 'pokemon', 'magic', 'one-piece', 'yugioh'), or null",
  "confidence": a number from 0.0 to 1.0 for your own confidence in this identification
}

The card number is the single most useful field - read it carefully, it often disambiguates cards that otherwise share a name across sets and eras. If you cannot read a field clearly, use null rather than guessing - never fabricate a plausible-looking value."""
