/** Selection presentation and checkbox behaviour; process routing stays in SFSM. */
export function visibleSelectionOptions(options = []) {
  // The optional-question skip sentinel is a separate action, unlike the
  // genuine Forms choice "none_of_the_above" which must remain visible.
  return options.filter((option) => option.value !== "__forms_skip__");
}

export function toggleSelectedValues(selected, changed, checked, exclusiveOptions = []) {
  const values = Array.isArray(selected) ? selected : [];
  if (!checked) return values.filter((value) => value !== changed);
  if (exclusiveOptions.includes(changed)) return [changed];
  // Selecting any ordinary checkbox deselects "None of the above".
  const ordinary = values.filter((value) => !exclusiveOptions.includes(value));
  return ordinary.includes(changed) ? ordinary : [...ordinary, changed];
}
