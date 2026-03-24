import axios from 'axios';

const API_URL = import.meta.env.VITE_BACKEND_URL + '/api';

const getPerformedBy = () => localStorage.getItem('adminUsername') || 'unknown';

export const createCustomRole = async (roleData) => {
  try {
    const response = await axiosInstance.post("/create-role/", {
      ...roleData,
      performed_by: getPerformedBy(), 
    });
    return response.data;
  } catch (error) {
    console.error(
      "Error creating custom role:",
      error.response?.data || error.message,
    );
    throw error;
  }
};

export const fetchAuditLogs = async (filters = {}) => {
  try {
    const params = new URLSearchParams(filters).toString();
    const response = await axiosInstance.get(
      `/audit-logs/${params ? "?" + params : ""}`
    );
    return response.data;
  } catch (error) {
    console.error(
      "Error fetching audit logs:",
      error.response?.data || error.message
    );
    throw error;
  }
};


export const getAllRoles = async () => {
    try {
        const response = await axios.get(API_URL + '/view-roles/');
        return response.data;
    } catch (error) {
        console.error('Error fetching roles:', error.response?.data || error.message);
        throw error;
    }
}

export const getAllDesignations = async (designationType) => {
    try {
        const response = await axios.post(API_URL + '/view-designations/', designationType);
        return response.data;
    } catch (error) {
        console.error('Error fetching designations:', error.response?.data || error.message);
        throw error;
    }
}

export const getAllDepartments = async () => {
    console.log(API_URL);
    console.log("yoooooooooooooooooooooooooooooooooooooooooooo12121212");
    try {
        const response = await axios.get(API_URL + '/departments/');
        return response.data;
    } catch (error) {
        console.error('Error fetching departments:', error.response?.data || error.message);
        throw error;
    }
}

export const getAllBatches = async () => {
    try {
        const response = await axios.get(API_URL + '/batches/');
        return response.data;
    } catch (error) {
        console.error('Error fetching batches:', error.response?.data || error.message);
        throw error;
    }
}