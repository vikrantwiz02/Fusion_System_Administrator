import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  Button,
  Text,
  Stack,
  Modal,
  Flex,
  rem,
  TextInput,
  MultiSelect,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import axios from "axios";
import { useMediaQuery } from "@mantine/hooks";
import { FaCheck, FaTimes } from 'react-icons/fa';

const EditUserRolePage = () => {
  const [username, setUsername] = useState("");
  const [userDetails, setUserDetails] = useState(null);
  const [roles, setRoles] = useState([]);
  const [currentRoles, setCurrentRoles] = useState([]);
  const [newRoles, setNewRoles] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const xIcon = <FaTimes style={{ width: rem(20), height: rem(20) }} />;
  const checkIcon = <FaCheck style={{ width: rem(20), height: rem(20) }} />;

  const API_URL = import.meta.env.VITE_BACKEND_URL;

  const fetchUserAndRoleDetails = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        API_URL + `/api/get-user-roles-by-username?username=${username}`
      );
      setUserDetails(response.data.user);
      setCurrentRoles(response.data.roles);
      setLoading(false);
    } catch (error) {
      setLoading(false);
      notifications.show({
        title: "Error",
        icon: xIcon,
        position: "top-center",
        withCloseButton: true,
        message: "Could not fetch user details. Please check the username.",
        color: "red",
      });
    }
  };

  const handleSubmit = async () => {
    try {
      const updatedRoles = [...currentRoles, ...newRoles].filter(
        (role, index, self) => self.indexOf(role) === index
      );
      console.log(updatedRoles);

      await axios.put(API_URL + `/api/update-user-roles/`, {
        username: username,
        roles: updatedRoles,
        performed_by: localStorage.getItem('adminUsername') || 'unknown',
      });

      notifications.show({
        title: "Success",
        position: "top-center",
        icon: checkIcon,
        withCloseButton: true,
        message: "User roles updated successfully.",
        color: "green",
      });
      setCurrentRoles(updatedRoles);
      fetchUserAndRoleDetails();
      setNewRoles([]);
      setIsOpen(false);
    } catch (error) {
      notifications.show({
        title: "Error",
        position: "top-center",
        icon: xIcon,
        withCloseButton: true,
        message: "Could not update user roles.",
        color: "red",
      });
    }
  };

  const handleRemoveRole = (role) => {
    setCurrentRoles((prevRoles) => prevRoles.filter((r) => r !== role));
  };

  const fetchAvailableRoles = async () => {
    try {
      const response = await axios.get(API_URL + `/api/view-roles`);
      setRoles(response.data);
    } catch (error) {
      console.log(error.response);
    }
  };

  useEffect(() => {
    fetchAvailableRoles();
  }, []);

  const handleEnterKeyPress = (event) => {
    if (event.key === "Enter") {
      fetchUserAndRoleDetails();
    }
  };

  useEffect(() => {
    document.addEventListener("keydown", handleEnterKeyPress);
    return () => {
      document.removeEventListener("keydown", handleEnterKeyPress);
    };
  }, [username]);

  const matches = useMediaQuery('(min-width: 768px)');

  return (
    <Box
      style={{
        backgroundColor: "#f0f0f0",
        minHeight: "100vh",
        padding: "1rem",
      }}
    >
      {/* Title Button */}
      <Flex
        justify="center"
        align="center"
        style={{
          marginBottom: "2rem",
        }}
      >
        <Button
          variant="gradient"
          size="xl"
          radius="xs"
          gradient={{ from: "blue", to: "cyan", deg: 90 }}
          w={matches && "500px"}
          style={{
            fontSize: "1.8rem",
            lineHeight: 1.2,
          }}
        >
          <Title
            order={1}
            align="center"
            style={{
              fontSize: "1.25rem",
              wordBreak: "break-word",
            }}
          >
            {"Edit User's Role"}
          </Title>
        </Button>
      </Flex>

      <Flex
        direction={{ base: "column", lg: "row" }}
        style={{
          gap: "2rem",
          justifyContent: "center",
        }}
      >
        {/* First Section - Username Input */}
        <Box style={{ width: "100%", flex: 1 }}>
          <Stack spacing="1rem">
            <TextInput
              label="Username"
              placeholder="Enter username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <Button onClick={fetchUserAndRoleDetails}>Fetch User Details</Button>
          </Stack>

          {userDetails && (
            <Box
              style={{
                width: "100%",
                padding: "1rem",
                marginTop: "1rem",
                borderRadius: "8px",
                boxShadow: "0px 4px 12px rgba(0, 0, 0, 0.1)",
                position: "relative",
                backgroundColor: "white",
              }}
            >
              {/* Status Label at the top right */}
              <Box
                style={{
                  position: "absolute",
                  top: "0.5rem",
                  right: "0.5rem",
                  backgroundColor: userDetails.is_active ? "green" : "red",
                  color: "white",
                  padding: "0.25rem 0.5rem",
                  borderRadius: "4px",
                }}
              >
                {userDetails.is_active ? "Active" : "Non-Active"}
              </Box>

              {/* User Details */}
              <Stack spacing="1rem">
                <Text style={{ fontSize: "1.1rem", fontWeight: "bold" }}>
                  Name: {userDetails.first_name}
                </Text>
                <Text style={{ fontSize: "1.1rem", fontWeight: "bold" }}>Roll No: {userDetails.username}</Text>

                {/* Display formatted date joined */}
                <Text style={{ fontSize: "1.1rem", fontWeight: "bold" }}>
                  Date Joined: {new Date(userDetails.date_joined).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </Text>
              </Stack>
            </Box>
          )}
        </Box>

        {/* Second Section - Current Roles and New Role Selection */}
        <Box
          style={{
            width: "100%",
            flex: 1,
            padding: "1rem",
            backgroundColor: "#fff",
            borderRadius: "8px",
            boxShadow: "0px 4px 12px rgba(0, 0, 0, 0.1)",
            maxHeight: "400px",
          }}
        >
          {loading ? (
            <Text>Loading roles...</Text>
          ) : userDetails ? (
            <Box>
              <Text style={{ fontSize: "1.25rem", fontWeight: "bold" }}>Current Roles:</Text>
              {/* Scrollable roles section */}
              <Box
                style={{
                  maxHeight: "200px",
                  overflowY: "auto",
                  paddingRight: "1rem",
                }}
              >
                <Stack spacing="sm">
                  {currentRoles.map((role) => (
                    <Flex
                      key={role}
                      justify={"space-between"}
                      align={"center"}
                      style={{
                        padding: "0.5rem 1rem",
                        borderRadius: "4px",
                        fontWeight: "bold",
                        cursor: "pointer",
                        transition: "background-color 0.2s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = "#f0f0f0";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = "transparent";
                      }}
                    >
                      <Text>{role.name}{role.basic ? "(Base)" : ""}</Text>
                      <Button
                        variant="outline"
                        color="red"
                        disabled={role.basic}
                        onClick={() => handleRemoveRole(role)}
                      >
                        Remove
                      </Button>
                    </Flex>
                  ))}
                </Stack>
              </Box>

              {/* Non-scrollable section */}
              <MultiSelect
                label="Add new role"
                placeholder="Select roles"
                data={roles.map((role) => ({
                  value: role.name,
                  label: `${role.name}${role.basic ? "(Base)" : ""}`,
                }))}
                value={newRoles}
                onChange={setNewRoles}
                searchable
                clearable
              />

              <Button
                color="blue"
                onClick={() => setIsOpen(true)}
                mt="1rem"
                fullWidth
              >
                Confirm Changes
              </Button>
            </Box>
          ) : (
            <Text>No user details found</Text>
          )}
        </Box>
      </Flex>

      {/* Confirmation Modal */}
      <Modal
        opened={isOpen}
        onClose={() => setIsOpen(false)}
        title="Confirm Changes"
      >
        <Text>Are you sure you want to update the user roles?</Text>
        <Flex justify="flex-end" gap="1rem" mt="1rem">
          <Button variant="default" onClick={() => setIsOpen(false)}>
            Cancel
          </Button>
          <Button color="blue" onClick={handleSubmit}>
            Confirm
          </Button>
        </Flex>
      </Modal>
    </Box>
  );
};

export default EditUserRolePage;