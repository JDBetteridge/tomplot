"""
Convert LFRic logged data into the transportdrake global output format.
"""

import numpy as np
import pandas as pd
from netCDF4 import Dataset

all_errors = ['Min-initial', 'Max-initial', 'L2-initial', 'L2-final',
              'Rel-L2-error', 'Dissipation', 'Dispersion']

def convert_global_output(target_dir, source_dirs, mode='transport_stats',
                          dt=None, run_params=None):

    # ------------------------------------------------------------------------ #
    # Checks
    # ------------------------------------------------------------------------ #

    if run_params is None:
        run_params = {}
    elif type(run_params) is not dict:
        raise TypeError(f'run_params should be a dict not type {type(run_params)}')

    if type(source_dirs) is not list:
        source_dirs = [source_dirs]
        # Convert all params into lists
        for param_key, param_value in run_params.items():
            run_params[param_key] = [param_value]
    else:
        for param_key, param_value in run_params.items():
            if type(param_value) is not list:
                raise TypeError(f'If source_dirs argument is a list, each '+
                                f'param in run_params should also be a list, '+
                                f'but {param_key} is type {type(param_value)}')
            elif len(param_value) != len(source_dirs):
                raise ValueError(f'List for {param_key} should be of length '
                                 f'{len(source_dirs)} to match length of source_dirs')

    if mode not in ['transport_stats','gungho_mass']:
        raise ValueError('Converter mode should be "transport_stats" or "gungho"')

    # ------------------------------------------------------------------------ #
    # Read data into pandas dataframe
    # ------------------------------------------------------------------------ #

    if mode == 'transport_stats':
        col_names = ['day','timestamp','log_level','log_file','str1','str2',
                     'str3','str4','time','measure_name','variable','str5',
                     'measure_value']
    elif mode == 'gungho_mass':
        col_names = ['day','timestamp','log_level','log_file','str1','str2',
                     'str3','str4','str5','species_str','timestage1','timestage2',
                     'str6','str7','str8','timestep', 'mass']
    else:
        raise NotImplementedError(f'mode {mode} not implemented')

    data_frame_list = []

    for source_dir in source_dirs:
        file_name = f'{source_dir}/raw_data/output.log'
        print(f'Reading in {file_name}')
        # read in raw data from log file
        # skipinitialspace=True means that bunches of spaces are delimiters
        raw_data = pd.read_csv(file_name, header=None, sep=' ',
                               skipinitialspace=True, names=col_names)

        # -------------------------------------------------------------------- #
        # Data manipulations
        # -------------------------------------------------------------------- #

        if mode == 'gungho_mass':
            # Species are currently a string 'i,'. Lose the comma
            species = [str(species_str[0]) for species_str in raw_data['species_str'].values]
            raw_data['species'] = species
            # Convert mass data to floats
            raw_data['mass'] = raw_data['mass'].astype(float)
            # Combine point in timestep values into single value
            point_in_timestep = [f'{point1}_{point2}' for (point1, point2)
                                 in zip(raw_data['timestage1'].values,
                                        raw_data['timestage2'].values)]
            raw_data['timestage'] = point_in_timestep
            if dt is not None:
                raw_data['time'] = raw_data['timestep'].astype(float) * dt
            else:
                raw_data['time'] = raw_data['timestep'].astype(float)
            # Change values before initial time step to be after time step zero
            raw_data.loc[raw_data.timestage == 'Before_timestep', 'time'] = 0.0
            raw_data.loc[raw_data.timestage == 'Before_timestep', 'timestage'] = 'After_timestep'
            # Combine all moisture species to get total moisture mass
            time_list = []
            stage_list = []
            mass_list = []
            unique_times = raw_data.time.unique()
            for time in unique_times:
                unique_stages = raw_data[raw_data.time == time].timestage.unique()
                for stage in unique_stages:
                    filtered_data = raw_data[(raw_data.time == time) &
                                             (raw_data.timestage == stage)].mass
                    total_mass = np.sum(filtered_data)
                    time_list.append(time)
                    stage_list.append(stage)
                    mass_list.append(total_mass)
            total_data = pd.DataFrame({'timestage':stage_list,
                                       'time':time_list,
                                       'mass':mass_list,
                                       'species':['total']*len(mass_list)})
            raw_data = pd.concat([raw_data, total_data], ignore_index=True, axis=0)

        elif mode == 'transport_stats':
            # No manipulations needed for now
            pass
        else:
            raise NotImplementedError(f'mode {mode} not implemented')

        data_frame_list.append(raw_data)

    # ------------------------------------------------------------------------ #
    # Create global_output.nc
    # ------------------------------------------------------------------------ #

    output_file_name = f'{target_dir}/global_output.nc'
    output_data = Dataset(output_file_name, 'w')

    # Create dimensions
    output_data.createDimension('run_id', None)
    output_data.createDimension('time', None)
    output_data.createVariable('run_id', int, ('run_id',))
    output_data.createVariable('time', float, ('run_id', 'time'))

    # Add run_id variable
    output_data.variables['run_id'][:] = range(len(data_frame_list))

    # Create groups for variables
    if mode == 'gungho_mass':

        # Add time variable
        for i, df in enumerate(data_frame_list):
            for j, t in enumerate(df.time.unique()):
                output_data.variables['time'][i,j] = float(t)

        # Extract unique species and measures
        unique_species = data_frame_list[0].species.unique()
        unique_measures = data_frame_list[0].timestage.unique()

        # Loop through species, adding groups
        for species in unique_species:
            output_data.createGroup(species)
            output_data[species].createGroup('errors')
            output_data[species].createGroup('global_quantities')

            # Loop through measures and add values
            for measure in unique_measures:
                output_data[species]['global_quantities'].createVariable(measure, float, ('run_id', 'time'))

                for i, df in enumerate(data_frame_list):
                    data_table = df[(df.species == species) & (df.timestage == measure)]
                    # Sort by time step and extract mass
                    data = data_table.sort_values('time').mass.values
                    # Fill to the end
                    idx0 = len(df.time.unique()) - len(data)
                    # TODO: this is so much slower than slicing. Is there a quicker way?
                    # I got into a mess with masked arrays and whether I was assigning
                    # to a pointer or not...
                    for k, datum in enumerate(data):
                        output_data[species]['global_quantities'][measure][i,k+idx0] = datum

    elif mode == 'transport_stats':

        unique_variables = data_frame_list[0].variable.unique()

        # Loop through variables, adding groups
        for variable in unique_variables:
            output_data.createGroup(variable)

        for param_key, param_value in run_params.items():
            # Assume that all members of param_value are the same type!
            output_data.createVariable(param_key, type(param_value[0]), ('run_id',))
            output_data.variables[param_key][:] = param_value

        # Loop through data and separate into error and global data frames
        for i, df in enumerate(data_frame_list):
            error_data = df[df.measure_name.isin(all_errors)]
            quant_data = df[~df.measure_name.isin(all_errors)]

            # ---------------------------------------------------------------- #
            # Error data
            # ---------------------------------------------------------------- #

            unique_variables = error_data.variable.unique()

            # Create groups for the first time
            if i == 0:
                output_data.createDimension('error_time', None)
                output_data.createVariable('error_time', float, ('run_id','error_time'))

                for variable in unique_variables:
                    output_data[variable].createGroup('errors')

            # Errors
            times = error_data.sort_values('time').time.unique()

            # TODO: find out how to do this properly
            # I couldn't work out how to get this to work with slices
            for j, t in enumerate(times):
                output_data['error_time'][i,j] = t

            # Loop through variables
            for variable in unique_variables:
                unique_measures = error_data[error_data.variable == variable].measure_name.unique()

                for measure in unique_measures:

                    # Create variables for the first time
                    if i == 0:
                        output_data[variable]['errors'].createVariable(measure, float, ('run_id', 'error_time'))

                    data_table = error_data[(error_data.variable == variable) &
                                            (error_data.measure_name == measure)]
                    # Sort by time step and extract mass
                    data = data_table.sort_values('time').measure_value.values
                    # Fill to the end
                    idx0 = len(error_data.time.unique()) - len(data)
                    # TODO: this is so much slower than slicing. Is there a quicker way?
                    # I got into a mess with masked arrays and whether I was assigning
                    # to a pointer or not...
                    for k, datum in enumerate(data):
                        output_data[variable]['errors'][measure][i,k+idx0] = datum

            # ---------------------------------------------------------------- #
            # Global quantity data
            # ---------------------------------------------------------------- #

            unique_variables = quant_data.variable.unique()
            times = quant_data.sort_values('time').time.unique()
            # TODO: find out how to do this properly
            # I couldn't work out how to get this to work with slices
            for j, t in enumerate(times):
                output_data['time'][i,j] = t

            # Loop through variables
            for variable in unique_variables:
                if i == 0:
                    output_data[variable].createGroup('global_quantities')

                unique_measures = quant_data[quant_data.variable == variable].measure_name.unique()

                for measure in unique_measures:

                    # Create variables for the first time
                    if i == 0:
                        output_data[variable]['global_quantities'].createVariable(measure, float, ('run_id', 'time'))

                    data_table = quant_data[(quant_data.variable == variable) &
                                            (quant_data.measure_name == measure)]
                    # Sort by time step and extract mass
                    data = data_table.sort_values('time').measure_value.values
                    # Fill to the end
                    idx0 = len(quant_data.time.unique()) - len(data)
                    # TODO: this is so much slower than slicing. Is there a quicker way?
                    # I got into a mess with masked arrays and whether I was assigning
                    # to a pointer or not...
                    for k, datum in enumerate(data[:]):
                        output_data[variable]['global_quantities'][measure][i,k+idx0] = datum

    else:
        raise NotImplementedError(f'mode {mode} not implemented')

    output_data.close()