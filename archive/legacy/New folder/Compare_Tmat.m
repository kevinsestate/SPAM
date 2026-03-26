%% Logistics
clear all
set(groot,'defaultTextInterpreter','latex')
set(groot, 'defaultAxesTickLabelInterpreter','latex');
set(groot, 'defaultLegendInterpreter','latex');
set(groot,'defaultAxesFontSize',16)
set(groot,'defaultLineLineWidth', 1.2);
format compact
fig_cnt=0;
c0=physconst('LightSpeed'); ep0=8.854e-12; mu0=1/c0^2/ep0; eta0=sqrt(mu0/ep0);

%% Parameters
f0=24e9; d_mil=60;

% Derived
lam0=c0/f0; k0=2*pi/lam0; d=d_mil/39.37*1e-3; k0d=k0*d;


%% Extraction and Material Settings
% fname_extraction='SPAM_Scat_Mat_er2_mur3.mat';
% erv=[2,0,0,2,1e-6,2]; mrv=[3,0,0,3,0,3];
% fname_extraction='SPAM_Scat_Mat_er225_mur333.mat';
% erv=[2,0,0,2,0,5]; mrv=[3,0,0,3,0,3];
% fname_extraction='SPAM_Scat_Mat_er225_mur343.mat';
% erv=[2,0,0,2,0,5]; mrv=[3,0,0,4,0,3];
% fname_extraction='SPAM_Scat_Mat_er201205_mur343.mat';
% erv=[2,0,1,2,0,5]; mrv=[3,0,0,4,0,3];
% fname_extraction='SPAM_Scat_Mat_er210205_mur343.mat';
% erv=[2,1,0,2,0,5]; mrv=[3,0,0,4,0,3];
% fname_extraction='SPAM_Scat_Mat_er200215_mur343.mat';
% erv=[2,0,0,2,1,5]; mrv=[3,0,0,4,0,3];
% fname_extraction='SPAM_Scat_Mat_er201205_allj_mur343_allj.mat';
% erv=[2,0,1,2,0,5].*(1-1j); mrv=[3,0,0,4,0,3].*(1-1j);
% fname_extraction='SPAM_Scat_Mat_erfull_murdiag.mat';
% erv=[2,1.5,1,2,0.5,5]; mrv=[3,0,0,4,0,3];
% fname_extraction='SPAM_Scat_Mat_erfull_murfull.mat';
% erv=[2,1.5,1,2,0.5,5]; mrv=[1.25,1,0.5,4,0.75,3];
fname_extraction='SPAM_Scat_Mat_erfull_murfull_cutoff.mat';
erv=[2,1.5,1,2,0.5,5]; mrv=[3,1,0,4,2,1];

% Measurement Data Extraction
load(fname_extraction,'S_SPAM','theta_deg');

%% Compute Measured ABCD matrix
[T_Meas]=f_spams2abcd(S_SPAM,theta_deg);
[T_Theory]=f_mater2abcd(erv,mrv,theta_deg,k0d);
[ErrT]=f_errT(T_Meas,T_Theory);

%% Plotting
[fig_cnt,~]=newfig(fig_cnt);
plot(theta_deg,ErrT)

%% Function - Plotting 
function [figure_count,figure_handle]=newfig(figure_count)
    figure_count=figure_count+1;
    figure_handle=figure(figure_count);
    clf(figure_count);
    hold on;
    grid on;
end










