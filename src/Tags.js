// @flow strict

import * as React from "react";

import Badge from "react-bootstrap/Badge";

type Props = {
  tags: Array<string>,
};

const colorLookup = {
  Regular: "secondary",
  Scholars: "success",
  "2x Speed": "danger",
  Zoom: "info",
  Transfer: "primary",
};

export default function Tags({ tags }: Props) {
  return (
    <>
      {tags.map((tag) => (
        <Badge
          className="float-right"
          pill
          variant={colorLookup[tag] ?? "dark"}
          key={tag}
        >
          {tag}
        </Badge>
      ))}
    </>
  );
}
