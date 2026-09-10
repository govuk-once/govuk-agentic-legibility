# Service Studio

Service Studio is an experimental working prototype of the frontend development relating to the canonical schema RFC. It will demonstrate how to onboard a service to the service studio tool and secondly, how to create, edit and save schemas.

Right now it is in its early development.

## Install

Install the project dependencies:

```sh
pnpm install
```

## Run

Start the development server:

```sh
pnpm run dev
```

Open the local address shown in the terminal.

## Routes

`/edit` contains the current visual journey graph editor.

`/onboard` contains the onboarding journey.

### Onboard
This route focuses on the development of the onboarding process for services. Currently, this includes how to generate canonical schemas using an LLM to automate the process. This is deliberately staged as a separate route so the UX of this process can be developed independent of the graph editor features.

Onboarding allows you to enter a title, description, supporting prompt request and any supporting documents for the LLM to generate the schema. This can then be downloaded at the end. For user testing purposes the aim is to explore what features are required to get consistent schema generations. Once this is determined, this process will be joined more seamlessly with the graph editor and negate the need to download a schema.

### Graph Editor
Steps can be added, edited, reordered and removed, and the journey graph updates from the same step list. Branching is currently a placeholder based on where steps sit in the list, rather than the real canonical schema. Next steps:

* Load real schemas to test the graph against real data
* Replace the placeholder branching with a schema driven version
* Join this up with the onboarding route once its UX is settled
