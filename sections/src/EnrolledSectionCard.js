/* eslint-disable no-nested-ternary,react/no-array-index-key */
// @flow strict

import { useContext } from "react";
import { CardDeck } from "react-bootstrap";
import Button from "react-bootstrap/Button";
import Card from "react-bootstrap/Card";
import * as React from "react";
import { Link } from "react-router-dom";
import type { Section } from "./models";
import { sectionTitle } from "./models";
import SectionJoinCallButtons from "./SectionJoinCallButtons";
import SectionTextFieldRow from "./SectionTextFieldRow";
import SectionCard from "./SectionCard";
import StateContext from "./StateContext";
import Tags from "./Tags";
import useStateAPI from "./useStateAPI";

type Props = {
  section: Section,
};

function sentenceList(items: Array<React.MixedElement>, isStaff: ?boolean) {
  const also = isStaff ? null : "also";
  if (items.length === 0) {
    return "No one else has joined this section yet.";
  } else if (items.length === 1) {
    return (
      <>
        {items[0]} has {also} joined this section.
      </>
    );
  } else if (items.length === 2) {
    return (
      <>
        {items[0]} and {items[1]} have {also} joined this section.
      </>
    );
  } else {
    const allButLast = items.slice(0, items.length - 1);
    return (
      <>
        {allButLast.map((item, i) => (
          <span key={i}>{item}, </span>
        ))}
        and {items[items.length - 1]} have {also} joined this section.
      </>
    );
  }
}

//help
export default function EnrolledSectionCard({ section }: Props) {
  const state = useContext(StateContext);
  const isStaff = state.currentUser?.isStaff;
  const abandonSection = useStateAPI("unassign_section");
  const leaveSection = useStateAPI("leave_section");
  const updateSectionDescription = useStateAPI("update_section_description");
  const updateSectionCallLink = useStateAPI("update_section_call_link");
  const updateSectionEnrollmentCode = useStateAPI(
    "update_section_enrollment_code"
  );

  return (
    <Card>
      <Card.Header>
        <h5 className="mb-n1">
          {sectionTitle(section)}
          <Tags tags={section.tags} />
        </h5>
      </Card.Header>
      <Card.Body>
        <Card.Text>
          <CardDeck>
            <SectionCard key={section.id} section={section} />
          </CardDeck>
        </Card.Text>
        {isStaff ? (
          <SectionTextFieldRow
            textarea
            initial={section.description}
            placeholder="Introduce yourself (max 255 characters)!"
            onSave={(description) =>
              updateSectionDescription({
                section_id: section.id,
                description,
              })
            }
          />
        ) : section.description ? (
          <Card.Text>{section.description}</Card.Text>
        ) : null}
        {isStaff &&
          <SectionTextFieldRow
            key={section.id}
            initial={section.callLink}
            placeholder={`Your Zoom Link for ${section.name} (optional)`}
            onSave={(callLink) =>
              updateSectionCallLink({
                section_id: section.id,
                call_link: callLink,
              })
            }
          />
          }
        {isStaff && section.canSelfEnroll && (
          <>
            <hr />
            <SectionTextFieldRow
              initial={section.enrollmentCode}
              placeholder="Enrollment Code (optional)"
              onSave={(enrollmentCode) =>
                updateSectionEnrollmentCode({
                  section_id: section.id,
                  enrollment_code: enrollmentCode,
                })
              }
            />
          </>
        )}
        {!isStaff && (
          <p>
            You have enrolled in{" "}
            {section.staff == null ? "a" : `${section.staff.name}'s`} section!{" "}
          </p>
        )}
        <p>
          {sentenceList(
            section.students
              .filter((student) => student.email !== state.currentUser?.email)
              .map((student) => <>{student.name}</>),
            isStaff
          )}
        </p>
        <p>
          {isStaff ? (
            <Link to={`/section/${section.id}`}>
              <Button variant="success">Enter Section</Button>
            </Link>
          ) : (
            <SectionJoinCallButtons section={section} />
          )}
        </p>
        {(isStaff
          ? state.config[`canTutorsChange${section.name}`] 
          : state.config[`canStudentsChange${section.name}`]) && ( 
          <Button
            variant="danger"
            size="sm"
            onClick={() =>
              isStaff
                ? abandonSection({ section_id: section.id })
                : leaveSection({ target_section_id: section.id })
            }
          >
            {isStaff ? "Abandon Section" : "Leave Section"}
          </Button>
        )}
      </Card.Body>
    </Card>
  );
}
