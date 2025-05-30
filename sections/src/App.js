/* eslint-disable react/no-array-index-key */
// @flow strict

import { useCallback, useEffect, useState } from "react";
import * as React from "react";
import Container from "react-bootstrap/Container";

import Nav from "react-bootstrap/Nav";
import Navbar from "react-bootstrap/Navbar";
import NavDropdown from "react-bootstrap/NavDropdown";
import { BrowserRouter as Router, Link, Route, Switch } from "react-router-dom";
import LabPage from "./LabPage";
import DiscPage from "./DiscPage";
import TutoringPage from "./TutoringPage";
import AdminPage from "./AdminPage";
import HistoryPage from "./HistoryPage";
import MainPage from "./MainPage";

import "bootstrap/dist/css/bootstrap.css";
import MessageContext from "./MessageContext";
import Messages from "./Messages";
import type { ID, State } from "./models";
import SectionPage from "./SectionPage";
import StateContext from "./StateContext";
import useAPI from "./useStateAPI";

export default function App(): React.Node {
  const [state, setState] = useState<?State>(null);
  const [messages, setMessages] = useState<Array<string>>([]);

  const pushMessage = useCallback(
    (message) => setMessages((currMessages) => currMessages.concat([message])),
    []
  );

  const updateState = (newState: State) => {
    // preserve ordering of sections, if possible
    if (state == null || newState.sections.length !== state?.sections.length) {
      setState(newState);
      return;
    }
    const sections = Array(newState.sections.length);
    const lookup = new Map<ID, number>();
    state.sections.forEach((section, i) => lookup.set(section.id, i));
    let ok = true;
    newState.sections.forEach((section) => {
      const i = lookup.get(section.id);
      if (i == null) {
        ok = false;
        return;
      }
      sections[i] = section;
    });
    if (ok) {
      // eslint-disable-next-line no-param-reassign
      newState.sections = sections;
    }
    setState(newState);
  };

  const refreshState = useAPI("refresh_state", updateState);

  useEffect(() => {
    if (state == null) {
      refreshState();
    }
  }, [state, refreshState]);

  if (state == null) {
    return null;
  }

  const is61A = state.course === "CS 61A";

  return (
    <Router>
      <Navbar bg="info" variant="dark" expand="md">
        <Link to="/">
          <Navbar.Brand>
            <b>{state.course}</b> Sections
          </Navbar.Brand>
        </Link>
        <Navbar.Toggle aria-controls="navbar" />
        <Navbar.Collapse id="navbar">
          <Nav className="mr-auto">
            <Link to="/" className="nav-link active">
              Home
            </Link>
            {state.currentUser?.isStaff === false && (
              <Link to="/history" className="nav-link active">
                History
              </Link>
            )}
            {is61A && (
              <Nav.Link href="https://cs61a.org/staff/" target="_blank" active>
                Staff
              </Nav.Link>
            )}
            {/* {is61A && (
              <Nav.Link
                href="https://oh.cs61a.org/party"
                target="_blank"
                active
              >
                Study Groups
              </Nav.Link>
            )} */}
            {
              <Link to="/lab" className="nav-link active">
              Lab
            </Link>
            }
            {
              <Link to="/disc" className="nav-link active">
              Discussion
            </Link>
            }
            {
              <Link to="/tutoring" className="nav-link active">
              Tutoring
            </Link>
            }
            {state.currentUser?.isAdmin === true && 
            (
              <Link to="/admin" className="nav-link active">
                Admin
              </Link>
            )}
          </Nav>
          <Nav className="mr-sm-2">
            {state.currentUser != null ? (
              <NavDropdown title={state.currentUser.name} active>
                <NavDropdown.Item href="/oauth/logout">
                  Log out
                </NavDropdown.Item>
              </NavDropdown>
            ) : null}
          </Nav>
        </Navbar.Collapse>
      </Navbar>
      <Messages messages={messages} onChange={setMessages} />
      <StateContext.Provider value={{ ...state, updateState }}>
        <MessageContext.Provider value={{ pushMessage }}>
          <Switch>
            <Route exact path="/">
              <MainPage />
            </Route>
            <Route path="/history">
              <HistoryPage />
            </Route>
            <Route path="/user/:id">
              {({ match }) => <HistoryPage userID={match.params.id} />}
            </Route>
            <Route path="/lab">
              <LabPage />
            </Route>
            <Route path="/disc">
              <DiscPage />
            </Route>
            <Route path="/tutoring">
              <TutoringPage />
            </Route>
            <Route path="/admin">
              <AdminPage />
            </Route>
            <Route path="/section/:id">
              {({ match }) => <SectionPage id={match.params.id} />}
            </Route>
            <Route path="*">
              <Container>Error: Page not found</Container>
            </Route>
          </Switch>
        </MessageContext.Provider>
      </StateContext.Provider>
    </Router>
  );
}
