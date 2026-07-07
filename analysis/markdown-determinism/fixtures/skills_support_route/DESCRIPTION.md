# Skills support route

## Purpose

Test whether a model can execute branching service logic when route selection
depends on interpreting service-specific definitions and calculating values from
repeated records.

This is a synthetic service. The rules are defined entirely in `instructions.txt`;
the model should not need external policy knowledge.

## Increment from the previous fixture

`address_history_five_year` introduced written business rules, a derived temporal
boundary, and inclusion or exclusion of records.

This fixture adds:

- multiple information sources: an authoritative FLEX record and a conversation
- explicit source-precedence rules
- route precedence: identity, then education, then employment, then not eligible
- interpretation of a service-specific definition of employer-required internal
  training
- job classification from primary duties rather than job title
- an 8-week repeated-data calculation with an excluded unpaid week
- a market-rate comparison determined by the interpreted job group
- branch-specific output: `education_details` or `employment_details`
- a near-boundary pay result, where the selected job group changes the decision

## Expected decision path

1. FLEX confirms identity, so manual review is not selected.
2. The course otherwise looks eligible, but it is mandatory for the current job
   and restricted to the employer's staff.
3. The course is therefore employer-required internal training and the education
   route is not selected.
4. Employment must then be assessed.
5. Despite the title `Junior Data Analyst`, 80% of the person's normal work is
   account, access, incident and device support.
6. The job group is therefore `technical_support`, with a £510 weekly market-rate
   floor.
7. The fully unpaid sickness week ending 7 June is excluded from both averages.
8. The remaining 7 weeks average 17.57 paid hours and £512.14 gross pay.
9. The fixed-term contract exceeds 26 weeks.
10. The employment route is selected.

A `data_analysis` classification would apply a £650 floor and change the outcome.
Including the unpaid sickness week would also reduce the calculated averages. The
fixture therefore has several plausible but incorrect decision paths.

## Dimensions exercised

| Dimension | What this fixture adds |
| --- | --- |
| Read | Reconciles an authoritative FLEX record with a longer conversation |
| Write | Still only submits a form; no official record is changed |
| Authentication | Uses verified identity as the first route gate |
| Flow | Applies ordered branching across four possible routes |
| Loop | Processes eight weekly pay and hours records |
| Payment | No payment |
| Interpretation | Applies course, job-group, source-precedence and market-rate rules |
