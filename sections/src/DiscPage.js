/* eslint-disable react/no-array-index-key */
// @flow strict

import * as React from "react";
import Button from "react-bootstrap/Button";

import Col from "react-bootstrap/Col";
import Container from "react-bootstrap/Container";
import Jumbotron from "react-bootstrap/Jumbotron";
import { useContext } from "react";
import Row from "react-bootstrap/Row";
import ReactMarkdown from "react-markdown";
import styled from "styled-components";
import EnrolledSectionCard from "./EnrolledSectionCard";
import ToggleSwitch from "./ToggleSwitch";

import type { Section, Time } from "./models";

import nullThrows from "./nullThrows";

import "bootstrap/dist/css/bootstrap.css";
import SectionCardGroup from "./SectionCardGroup";
import StateContext from "./StateContext";

const FlexLayout = styled.div`
  display: flex;
  align-items: center;
  height: 100%;
`;

export default function DiscPage(): React.Node {
  const state = useContext(StateContext);

  const timeKeyLookup = new Map<string, Array<[Time, Time]>>();
  const sectionsGroupedByTime = new Map<string, Array<Section>>();

  const discSections = state.sections.filter((section) => section.name === "Discussion");
  for (const section of discSections) {
    // const interval = section.slots.map((slot) => [
    //   slot.startTime,
    //   slot.endTime,
    // ]);
    // should this be an array of an array or just an array 
    const interval = [[section.startTime, section.endTime]]
    const key = interval.toString();
    if (!sectionsGroupedByTime.has(key)) {
      sectionsGroupedByTime.set(key, []);
      timeKeyLookup.set(key, interval);
    }
    nullThrows(sectionsGroupedByTime.get(key)).push(section);
  }

  const sortedIntervals: Array<Array<[Time, Time]>> = Array.from(
    timeKeyLookup.values()
  ).sort((t1, t2) => {
    for (let i = 0; i !== Math.max(t1.length, t2.length); ++i) {
      const [s1, e1] = t1[i] ?? [0, 0];
      const [s2, e2] = t2[i] ?? [0, 0];
      if (s1 === s2 && e1 === e2) {
        // pass
      } else if (s1 < s2 || (s1 === s2 && e1 < e2)) {
        return -1;
      } else {
        return 1;
      }
    }
    return 0;
  });

  // useLocal cookie helpers
  function getUseLocalCookieValue(): boolean {
    // check existence of the cookie
    if (
      document.cookie
        .split(";")
        .some((item) => item.trim().startsWith("useLocal="))
    ) {
      const cookieVal = document.cookie
        .split("; ")
        .find((row) => row.startsWith("useLocal="));
      // eslint-disable-next-line
      return cookieVal != undefined && cookieVal.split("=")[1] === "true";
    } else {
      // create the cookie and set it to true
      document.cookie = "useLocal=true; SameSite=lax; Secure";
      return false;
    }
  }

  function setUseLocalCookieValue(toSet) {
    const toSetString = toSet === true ? "true" : "false";
    document.cookie = `useLocal=${toSetString}; SameSite=lax; Secure`;
  }

  const toggleUseLocalDefault = getUseLocalCookieValue();

  // wrapper for tz toggle
  function useTimeToggle(initialValue = false) {
    const [value, setValue] = React.useState(initialValue);
    const toggle = React.useCallback(() => {
      setValue((v) => !v);
    }, []);
    return [value, toggle];
  }

  const [isTimeSwitchOn, timeSwitchToggled] = useTimeToggle();  // eslint-disable-line no-unused-vars

  function updateTimePreferences(useLocalTime) {
    setUseLocalCookieValue(useLocalTime);
    timeSwitchToggled();
  }


  return (
    <>
      <Jumbotron fluid>
        <Container>
          <Row>
            <Col>
              <h1 className="display-4">{state.course} Discussion Sections</h1>
            </Col>
            {state.currentUser == null ? (
              <Col>
                <FlexLayout>
                  <Button block variant="warning" size="lg" href="/oauth/login">
                    Sign in with OKPy
                  </Button>
                </FlexLayout>
              </Col>
            ) : null}
          </Row>
          {discSections.length === 0 ? (
              <ReactMarkdown>Course staff has not yet set up discussion sections.</ReactMarkdown>
            ) : null}
          {state.currentUser?.isStaff ? (
            // need to filter just by disc
            state.taughtSections
            .filter((section) => section.name === "Discussion")
            .map((section, i) => (
              <div key={section.id}>
                {i !== 0 && <br />}
                <EnrolledSectionCard section={section} />
              </div>
            ))
          ) : state.enrolledSections == null || state.enrolledSections.length === 0 ? null : (
            state.enrolledSections
              .filter((section) => section.name === "Discussion")
              .map((section) => (
                <EnrolledSectionCard key={section.id} section={section} />
              ))
          )}
        </Container>
      </Jumbotron>
      <Container>
        {sortedIntervals.length !== 0 ? (
          <ToggleSwitch
            defaultChecked={toggleUseLocalDefault}
            offText="Pacific"
            onText="Local"
            onChange={updateTimePreferences}
          />
        ) : null}
        {sortedIntervals.map((interval, i) => (
           // need to filter just by disc
          <Row key={i}>
            <Col>
              <SectionCardGroup
                sections={nullThrows(
                  sectionsGroupedByTime.get(interval.toString())
                )}
              />
              <br />
            </Col>
          </Row>
        ))}
      </Container>
    </>
  );
}