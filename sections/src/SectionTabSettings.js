// @flow strict

import "bootstrap/dist/css/bootstrap.css";
import { useState } from "react";
import * as React from "react";
import Button from "react-bootstrap/Button";
import Col from "react-bootstrap/Col";
import Table from "react-bootstrap/Table";
import Container from "react-bootstrap/Container";
import Row from "react-bootstrap/Row";
import { CardDeck } from "react-bootstrap";
import CalloutCard from "./CalloutCard";
import { getSectionStartTime, getSectionEndTime, getSectionDay } from "./models";
import type { Section } from "./models";
import InfoTooltip from "./InfoTooltip";
import useSectionAPI from "./useSectionAPI";

type Props = {
  section: Section,
};

export default function SectionTabSettings({ section }: Props) {
  const changeLocationAPI = useSectionAPI("update_section_location");
  const changeTagsAPI = useSectionAPI("update_section_tags");
  const changeTimeAPI = useSectionAPI("update_section_time");

  const handleSubmit = () => {
    if (formData["location"] !== section.location) {
      changeLocationAPI({
        section_id: section.id,
        new_location: formData["location"]
      });
    };

    if (formData["day"] !== getSectionDay(section)
      || formData["startTime"] !== getSectionStartTime(section)
      || formData["endTime"] !== getSectionEndTime(section)
    ) {
      changeTimeAPI({
        section_id: section.id,
        day: formData["day"],
        start_time: formData["startTime"],
        end_time: formData["endTime"]
      });
    };

    if (formData["tags"] !== section.tags.toString()) {
      changeTagsAPI({
        section_id: section.id,
        tags: formData["tags"]
      });
    };
  };

  type SettingsKey =
  | "location"
  | "day"
  | "startTime"
  | "endTime"
  | "tags";

  type FormData = {
    location: string,
    day: string,
    startTime: string,
    endTime: string,
    tags: string,
  };

  const settings: Array<{key: SettingsKey, label: string, tooltip: string}> = [
      { key: "location", label: "Location", tooltip: "Any text (Ex: Wheeler 150)" },
      { key: "day", label: "Day", tooltip: "Any of: [M, T, W, Th, F] (Ex: M)" },
      { key: "startTime", label: "Start Time", tooltip: "hh:mma/p Include leading 0 (Ex: 08:30a)" },
      { key: "endTime", label: "End Time", tooltip: "hh:mma/p Include leading 0 (Ex: 08:30a)" },
      { key: "tags", label: "Tags", tooltip: "Comma seperated tags (Ex: Tag A, Tag B)" }
  ];

  const [formData, setFormData] = useState<FormData>({
    location: section.location,
    day: getSectionDay(section),
    startTime: getSectionStartTime(section),
    endTime: getSectionEndTime(section),
    tags: section.tags.toString()
  });

  const handleChange = (key: SettingsKey, value: string) => {
    setFormData(prev => {
      switch (key) {
        case "location":
          return { ...prev, location: value };
        case "day":
          return { ...prev, day: value };
        case "startTime":
          return { ...prev, startTime: value };
        case "endTime":
          return { ...prev, endTime: value };
        case "tags":
          return { ...prev, tags: value };
        default:
          return prev; // unreachable
      }
    });
  }

  return (
    <Container>
      <br />
      <Row>
        <Col>
          <p>
            <CardDeck>
              <CalloutCard header="Warning!" body="You can modify section attributes here, but changes should be made infrequently and carefully.
              Please ensure that this is necessary before proceeding." />
            </CardDeck>
          </p>
        </Col>
      </Row>
    <Table striped hover>
      <thead>
        <tr>
          <th>Section Attribute</th>
          <th>Displayed Values</th>
        </tr>
      </thead>
      <tbody>
        {settings.map(({key, label, tooltip }) => (
          <tr key={key}>
            <td>
              {label}
              <InfoTooltip text={tooltip}/>
            </td>
            <td>
              <input
                type="text"
                value={formData[key]}
                onChange={(e) => handleChange(key, e.target.value)}
              />
            </td>
          </tr>
        ))}
      </tbody>
      <br/>
      <Button
        variant="primary"
        size="sm"
        onClick={handleSubmit}
      >
        Submit Changes
      </Button>
    </Table>
    </Container>)
}