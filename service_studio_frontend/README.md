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

`/onboard` is a blank route reserved for the onboarding journey.

### Onboard
This route will focus on the development of the onboarding rpocess of services. Currently, this includes how to generate canonical schemas using an LLM to automate the process. This is deliberately staged as a separarte route so the UX of this process can be developed independent of the graph editor features.

Onboarding allows you to enter a title, description, supporting promtp request and any supporting documents for the LLM to generate the schema. This can then be downloaded at the end. For user testing purposes the aim is to try explore what features are required to get consistent schema generations. Once this is determined this process will be joined more seamlessly with the graph editor and negate the need to download a schema.

### Graph Editor
This is currently in development. Right now it shows a simple static journey to test out the node designs and draggable features. Next Steps:
* Add edit features
* Enable changes to update both the graph and left hand text-based panel
* Loading of schemas to test features and graph vsiualisations
