#include <iostream>
#include <Conflict_prediction.h>
#include <Rvector3.h>

using namespace std;
using namespace Ver;
using namespace Maverick;

// Helper function to print Rvector3
void print_vector(const string& label, const Rvector3& vec)
{
    cout << label << ": [" << vec[0] << ", " << vec[1] << ", " << vec[2] << "]" << endl;
}

void test_tcpa(Real px, Real py, Real pz, Real vx, Real vy, Real vz, Real cyl_h, Real cyl_d, Real tmax)
{
    Conflict_prediction::Cyllinder_distance cyl_dist;
    cyl_dist.p[0] = px;
    cyl_dist.p[1] = py;
    cyl_dist.p[2] = pz;
    cyl_dist.v[0] = vx;
    cyl_dist.v[1] = vy;
    cyl_dist.v[2] = vz;
    cyl_dist.cyl_h = cyl_h;
    cyl_dist.cyl_d = cyl_d;

    cout << "\n=== TCPA Test ===" << endl;
    print_vector("Initial Relative Position [NED]", cyl_dist.p);
    print_vector("Initial Relative Velocity [NED]", cyl_dist.v);
    cout << "Cylinder Height: " << cyl_dist.cyl_h << endl;
    cout << "Cylinder Diameter: " << cyl_dist.cyl_d << endl;
    cout << "Maximum time: " << tmax << endl;

    Real tcpa = Conflict_prediction::compute_tcpa(cyl_dist, tmax);
    cout << "Computed TCPA: " << tcpa << " seconds" << endl;

    Real dist_at_tcpa = cyl_dist.compute_at(tcpa);
    cout << "Distance at TCPA: " << dist_at_tcpa << endl;
}

int main()
{
    cout << "======================================" << endl;
    cout << "Conflict Prediction Class Test Program" << endl;
    cout << "======================================" << endl;

    test_tcpa(
        0.0F, 0.0F, 0.0F, 
        0.0F, 0.0F, 0.0F, 
        1.0F, 2.0F,       
        30.0F);            
    test_tcpa(
        0.0F, 0.0F, 0.0F, 
        1.0F, 2.0F, 3.0F, 
        1.0F, 2.0F, 
        30.0F);
    test_tcpa(
        10.0F, 0.0F, 0.0F, 
        1.0F, 0.0F, 0.0F, 
        1.0F, 2.0F, 
        30.0F);
    test_tcpa(
        10.0F, 0.0F, 0.0F, 
        -1.0F, 0.0F, 0.0F, 
        1.0F, 2.0F, 
        30.0F);
    test_tcpa(
        30.0F, 30.0F, 20.0F, 
        -1.0F, -1.0F, 0.0F, 
        1.0F, 2.0F,
        60.0F);
    test_tcpa(
        30.0F, 0.0F, 50.0F, 
        0.0F, 0.0F, -1.0F, 
        1.0F, 1.0F,
        60.0F);

    cout << "\n======================================" << endl;
    cout << "Done" << endl;
    cout << "======================================" << endl;
    

    return 0;
}
