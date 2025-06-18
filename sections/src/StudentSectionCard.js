/* eslint-disable react/no-array-index-key */
// @flow strict

import { useContext, useState } from "react";
import * as React from "react";
import { Col } from "react-bootstrap";
import Button from "react-bootstrap/Button";

import Card from "react-bootstrap/Card";
import ListGroup from "react-bootstrap/ListGroup";
import { Link } from "react-router-dom";
import { sectionTitle } from "./models";
import type { Section } from "./models";
import SectionCard from "./SectionCard";
import StateContext from "./StateContext";
import Tags from "./Tags";
import useAPI from "./useStateAPI";

import ConfirmEnrollmentModal from "./ConfirmEnrollmentModal";

type Props = {
  section: Section,
};

export default function StudentSectionCard({
  section,
}: Props): React.MixedElement {
  const { config, currentUser, enrolledSections } = useContext(StateContext);
  const hasSpace = section.capacity > section.students.length;
  const enrolledInThisSection = enrolledSections?.some(
    (enrolledSection) => enrolledSection.id === section.id
  );

  const isStaff = currentUser?.isStaff;
  const teachingThisSection = currentUser?.email === section.staff?.email;

  const [modalShown, setModalShown] = useState(false);

  const joinSection = useAPI("join_section");
  const claimSection = useAPI("claim_section");
  const unassignSection = useAPI("unassign_section");

  const sectionText = (
    <>({section.capacity - section.students.length} spots left)</>
  );

  const title = sectionTitle(section);

  const joinSectionWorkflow = () => {
    if (section.needsEnrollmentCode || !config[`canStudentsChange${section.name}`]) { 
      setModalShown(true);
    } else {
      joinSection({ target_section_id: section.id });
    }
  };

  const onModalSubmit = (enrollmentCode) => {
    joinSection({
      target_section_id: section.id,
      enrollment_code: enrollmentCode,
    });
  };

  return (
    <>
      <Card
        border={enrolledInThisSection || teachingThisSection ? "primary" : null}
      >
        <Card.Body>
          <Card.Title>
          <Col>
              <Tags tags={section.tags} />
              {isStaff &&
                (section.staff == null
                  ? config[`canTutorsChange${section.name}`] && ( 
                    <>
                      <Button
                        className="float-left"
                        size="sm"
                        onClick={() => claimSection({ section_id: section.id })}
                      >
                        Claim
                      </Button>
                      <br />
                      <br />
                      </>
                    )
                  : (section.staff.email === currentUser?.email
                      ? config[`canTutorsChange${section.name}`] 
                      : config[`canTutorsReassign${section.name}`]) && ( 
                      <>
                      <Button
                        className="float-left"
                        size="sm"
                        variant="danger"
                        onClick={() =>
                          unassignSection({ section_id: section.id })
                        }
                      >
                        Unassign
                      </Button>
                      <br />
                      <br />
                      </>
                    ))}
            </Col>
            {isStaff ? (
              <Link to={`/section/${section.id}`}>{title}</Link>
            ) : (
              title
            )}
          </Card.Title>
          <Card.Subtitle>
            {Math.max(section.capacity - section.students.length, 0)}/
            {section.capacity} spaces left
          </Card.Subtitle>
          <Card.Text>{section.description}</Card.Text>
          <SectionCard key={section.id} section={section} />
        </Card.Body>
        {hasSpace &&
        !isStaff &&
        // checks if student is enrolled in that particular section
        (enrolledSections != null && enrolledSections.length > 0 && enrolledSections.some(s => s.name === section.name) ? config[`canStudentsChange${section.name}`] : config[`canStudentsJoin${section.name}`]) && 
        section.canSelfEnroll ? (
          <ListGroup variant="flush">
            <ListGroup.Item
              disabled={enrolledInThisSection}
              action={!enrolledInThisSection}
              onClick={joinSectionWorkflow}
            >
              {enrolledInThisSection ? (
                <div>Switch to Section {sectionText}</div>
              ) : (
                <span className="btn-link">
                  {(enrolledSections == null || enrolledSections.filter(s => s.name === section.name).length === 0)
                    ? "Join Section"
                    : "Switch to Section"}{" "}
                  {sectionText}
                </span>
              )}
            </ListGroup.Item>
          </ListGroup>
        ) : null}
      </Card>
      <ConfirmEnrollmentModal
        show={modalShown}
        section={section}
        onClose={() => setModalShown(false)}
        onSubmit={onModalSubmit}
      />
    </>
  );
}
