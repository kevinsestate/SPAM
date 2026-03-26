function [T]=f_mater2abcd(erv,mrv,theta_deg,k0d)

    epr=[erv(1),erv(2),erv(3);erv(2),erv(4),erv(5);erv(3),erv(5),erv(6)];
    mur=[mrv(1),mrv(2),mrv(3);mrv(2),mrv(4),mrv(5);mrv(3),mrv(5),mrv(6)];
    e=inv(epr); m=inv(mur);
    e_x =e(1,1); e_xy=e(1,2); e_zx=e(1,3);
                 e_y =e(2,2); e_yz=e(2,3);
                              e_z =e(3,3);
    m_x =m(1,1); m_xy=m(1,2); m_zx=m(1,3);
                 m_y =m(2,2); m_yz=m(2,3);
                              m_z =m(3,3);

    % Helpful Definitions
    px=sind(theta_deg);
    Ntheta=length(theta_deg);
    s_1 =e_xy*m_xy-e_x*m_y;
    s_2 =2*e_zx*m_y-e_yz*m_xy-e_xy*m_yz;
    s_3 =e_yz*m_yz-e_z*m_y;
    s_4 =e_y*m_xy-e_xy*m_y;
    s_5 =e_yz*m_y-e_y*m_yz;
    s_6 =e_x*m_xy-m_x*e_xy;
    s_7 =e_yz*m_x-e_x*m_yz+2*e_xy*m_zx-2*e_zx*m_xy;
    s_8 =e_z*m_xy-e_xy*m_z-2*e_yz*m_zx+2*e_zx*m_yz;
    s_9 =e_yz*m_z-e_z*m_yz;
    s_10=e_xy*m_xy-e_y*m_x;
    s_11=2*e_y*m_zx-e_yz*m_xy-e_xy*m_yz;
    s_12=e_yz*m_yz-e_y*m_z;
    
    % Polynomial Coefficients
    A0=(s_3.*s_12-s_5.*s_9).*px.^4+(s_3+s_12).*px.^2+1;
    A1=(s_2*s_12-s_5.*s_8-s_4*s_9+s_3*s_11).*px.^3+(s_2+s_11).*px;
    A2=(s_1*s_12-s_5.*s_7-s_4*s_8+s_2*s_11+s_3*s_10).*px.^2+s_1+s_10;
    A3=(s_1*s_11-s_5*s_6-s_4*s_7+s_2*s_10).*px;
    A4=ones(size(px)).*(s_1*s_10-s_4*s_6);
    
    % Solver Dispersion Equation
    pz=zeros(Ntheta,4);
    for ti=1:Ntheta
        pz(ti,:)=roots([A4(ti),A3(ti),A2(ti),A1(ti),A0(ti)]);
    end
    
    
    % Dispersion Matrix Components
    Gxx=s_1.*pz.^2+s_2.*px.*pz+s_3.*px.^2;
    Gxy=s_4.*pz.^2+s_5.*px.*pz;
    Gyx=1./pz.*(s_6.*pz.^3+s_7.*px.*pz.^2+s_8.*px.^2.*pz+s_9.*px.^3);
    Gyy=s_10.*pz.^2+s_11.*px.*pz+s_12.*px.^2;

    % Build Eigenvectors
    EDx=Gyy-Gxy+1;
    EDy=Gxx-Gyx+1;
    Ex=(e_x-px./pz.*e_zx).*EDx+e_xy.*EDy;
    Ey=(e_xy-px./pz.*e_yz).*EDx+e_y.*EDy;
    c0Bx=(px.*e_yz-pz.*e_xy).*EDx-pz.*e_y.*EDy;
    c0By=(pz.*e_x-px.*e_zx+px./pz.*(px.*e_z-pz.*e_zx)).*EDx+(pz.*e_xy-px.*e_yz).*EDy;
    eta0Jx=(m_xy-px./pz.*m_yz).*c0Bx+m_y.*c0By;
    eta0Jy=(px./pz.*m_zx-m_x).*c0Bx-m_xy.*c0By;
    V_Theory=zeros(4,4,Ntheta);
    Lambda=zeros(4,4,Ntheta);
    for ti=1:Ntheta
        Lambda(:,:,ti)=diag(exp(1j.*k0d.*pz(ti,:)));
        V_Theory(:,:,ti)=[Ex(ti,:);Ey(ti,:);eta0Jx(ti,:);eta0Jy(ti,:)];
        for modi=1:4 
            [~,maxi]=max(abs(V_Theory(:,modi,ti)));
            V_Theory(:,modi,ti)=V_Theory(:,modi,ti)./V_Theory(maxi,modi,ti);
        end
    end
    
    % Build ABCD
    T=zeros(4,4,Ntheta);
    for ti=1:Ntheta
        T(:,:,ti)=V_Theory(:,:,ti)*Lambda(:,:,ti)/V_Theory(:,:,ti);
    end

end
